# -*- coding: utf-8 -*-
from collections import OrderedDict

from django.contrib.contenttypes.fields import GenericRelation
from django.contrib.contenttypes.models import ContentType
from django.db.models import ProtectedError, FieldDoesNotExist
from django.db.models.fields.related import ForeignObjectRel
from django.utils.translation import ugettext_lazy as _
from rest_framework import serializers


class BaseNestedModelSerializer(serializers.ModelSerializer):
    def _extract_relations(self, validated_data):
        reverse_relations = OrderedDict()
        relations = OrderedDict()

        # Remove related fields from validated data for future manipulations
        for field_name, field in self.fields.items():
            if field.read_only:
                continue
            try:
                related_field, direct = self._get_related_field(field)
            except FieldDoesNotExist:
                continue

            if isinstance(field, serializers.ListSerializer) and \
                    isinstance(field.child, serializers.ModelSerializer):
                if field.source not in validated_data:
                    # Skip field if field is not required
                    continue

                validated_data.pop(field.source)

                reverse_relations[field_name] = (related_field, field.child)

            if isinstance(field, serializers.ModelSerializer):
                if field.source not in validated_data:
                    # Skip field if field is not required
                    continue

                if validated_data.get(field.source) is None:
                    if direct:
                        # Don't process null value for direct relations
                        # Native create/update processes these values
                        continue

                validated_data.pop(field.source)
                # Reversed one-to-one looks like direct foreign keys but they
                # are reverse relations
                if direct:
                    relations[field_name] = field
                else:
                    reverse_relations[field_name] = (related_field, field)

        return relations, reverse_relations

    def _get_related_field(self, field):
        model_class = self.Meta.model

        related_field = model_class._meta.get_field(field.source)
        if isinstance(related_field, ForeignObjectRel):
            return related_field.field, False
        return related_field, True

    def _get_serializer_for_field(self, field, **kwargs):
        kwargs.update({
            'context': self.context,
            'partial': self.partial,
        })
        return field.__class__(**kwargs)

    def _get_save_kwargs(self, instance, related_field):
        if related_field.many_to_many:
            save_kwargs = {}
        elif isinstance(related_field, GenericRelation):
            save_kwargs = self._get_generic_lookup(instance, related_field)
        else:
            save_kwargs = {related_field.name: instance}
        return save_kwargs

    def _get_generic_lookup(self, instance, related_field):
        return {
            related_field.content_type_field_name: ContentType.objects.get_for_model(instance),
            related_field.object_id_field_name: instance.pk,
        }


class NestedCreateMixin(BaseNestedModelSerializer):
    """
    Mixin adds nested create feature
    """
    def create(self, validated_data):
        relations, reverse_relations = self._extract_relations(validated_data)

        # Create direct relations (foreign key, one-to-one)
        for field_name, field in relations.items():
            serializer = self._get_serializer_for_field(
                field, data=self.initial_data[field_name])
            serializer.is_valid(raise_exception=True)
            validated_data[field.source] = serializer.save()

        # Create instance
        instance = super(NestedCreateMixin, self).create(validated_data)

        if reverse_relations:
            self.create_reverse_relations(instance, reverse_relations)

        return instance

    def create_reverse_relations(self, instance, reverse_relations):
        # Create reverse relations
        # many-to-one, many-to-many, reversed one-to-one
        for field_name, (related_field, field) in reverse_relations.items():
            save_kwargs = self._get_save_kwargs(instance, related_field)

            related_data = self.initial_data[field_name]

            # Expand to array of one item for one-to-one for uniformity
            if related_field.one_to_one:
                # Skip processing for empty data
                if related_data is None:
                    continue
                related_data = [related_data]

            # Create related instances
            new_related_instances = []
            for data in related_data:
                serializer = self._get_serializer_for_field(
                    field, data=data)
                serializer.is_valid(raise_exception=True)
                related_instance = serializer.save(**save_kwargs)
                new_related_instances.append(related_instance)

            if related_field.many_to_many:
                # Add m2m instances to through model via add
                m2m_manager = getattr(instance, field_name)
                m2m_manager.add(*new_related_instances)


class NestedUpdateMixin(BaseNestedModelSerializer):
    """
    Mixin adds update nested feature
    """
    default_error_messages = {
        'cannot_delete_protected': _(
            "Cannot delete {instances} because "
            "protected relation exists")
    }

    def prefetch_related_instances(self, field, related_data):
        model_class = field.Meta.model
        instances = model_class.objects.filter(
            pk__in=[
                d.get('pk') for d in related_data
                if d is not None and d.get('pk', None)
            ]
        )
        instances = {
            related_instance.pk: related_instance
            for related_instance in instances
        }
        return instances

    def update(self, instance, validated_data):
        relations, reverse_relations = self._extract_relations(validated_data)

        # Create or update direct relations (foreign key, one-to-one)
        if relations:
            for field_name, field in relations.items():
                model_class = field.Meta.model
                obj = model_class.objects.filter(
                    pk=self.initial_data[field_name].get('pk')).first()
                if obj:
                    serializer = self._get_serializer_for_field(
                        field, instance=obj,
                        data=self.initial_data[field_name])
                else:
                    serializer = self._get_serializer_for_field(
                        field, data=self.initial_data[field_name])
                serializer.is_valid(raise_exception=True)
                validated_data[field.source] = serializer.save()

        # Update instance
        instance = super(NestedUpdateMixin, self).update(
            instance, validated_data)

        if reverse_relations:
            self.update_reverse_relations(instance, reverse_relations)
            self.delete_reverse_relations_if_need(instance, reverse_relations)
        return instance

    def update_reverse_relations(self, instance, reverse_relations):
        # Update reverse relations:
        # many-to-one, many-to-many, reversed one-to-one
        for field_name, (related_field, field) in reverse_relations.items():
            related_data = self.initial_data[field_name]
            # Expand to array of one item for one-to-one for uniformity
            if related_field.one_to_one:
                if related_data is None:
                    # Skip processing for empty data
                    continue
                related_data = [related_data]

            instances = self.prefetch_related_instances(field, related_data)

            save_kwargs = self._get_save_kwargs(instance, related_field)

            new_related_instances = []
            for data in related_data:
                is_new = data.get('pk') is None
                if is_new:
                    serializer = self._get_serializer_for_field(
                        field, data=data)
                else:
                    pk = data.get('pk')
                    obj = instances[pk]
                    serializer = self._get_serializer_for_field(
                        field, instance=obj, data=data)

                serializer.is_valid(raise_exception=True)
                related_instance = serializer.save(**save_kwargs)
                if is_new:
                    data['pk'] = related_instance.pk
                    new_related_instances.append(related_instance)

            if related_field.many_to_many:
                # Add m2m instances via add
                m2m_manager = getattr(instance, field_name)
                m2m_manager.add(*new_related_instances)

    def delete_reverse_relations_if_need(self, instance, reverse_relations):
        # Reverse `reverse_relations` for correct delete priority
        reverse_relations = OrderedDict(
            reversed(list(reverse_relations.items())))

        # Delete instances which is missed in data
        for field_name, (related_field, field) in reverse_relations.items():
            model_class = field.Meta.model

            related_data = self.initial_data[field_name]
            # Expand to array of one item for one-to-one for uniformity
            if related_field.one_to_one:
                related_data = [related_data]

            # M2M relation can be as direct as reverse. For direct relation we
            # should use reverse relation name
            if related_field.many_to_many and \
                    not isinstance(related_field, ForeignObjectRel):
                related_field_lookup = {
                    related_field.rel.name: instance,
                }
            elif isinstance(related_field, GenericRelation):
                related_field_lookup = self._get_generic_lookup(instance, related_field)
            else:
                related_field_lookup = {
                    related_field.name: instance,
                }

            current_ids = [d.get('pk') for d in related_data if d is not None]
            try:
                pks_to_delete = list(
                    model_class.objects.filter(
                        **related_field_lookup
                    ).exclude(
                        pk__in=current_ids
                    ).values_list('pk', flat=True)
                )

                if related_field.many_to_many:
                    # Remove relations from m2m table before deleting
                    # It is necessary for correct m2m_changes signal handling
                    m2m_manager = getattr(instance, field_name)
                    m2m_manager.remove(*pks_to_delete)

                model_class.objects.filter(pk__in=pks_to_delete).delete()

            except ProtectedError as e:
                instances = e.args[1]
                self.fail('cannot_delete_protected', instances=", ".join([
                    instance for instance in instances]))
