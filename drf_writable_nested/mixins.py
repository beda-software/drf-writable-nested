# -*- coding: utf-8 -*-
from copy import copy
from collections import OrderedDict

from django.db.models import ProtectedError
from django.db.models.fields.related import ForeignObjectRel
from django.utils.translation import ugettext_lazy as _

from rest_framework import serializers


class SavePriorityMixin(serializers.Serializer):
    """
    This mixin adds ability for set `priority` param to serializer
    if `NestedCreateMixin`/`NestedUpdateMixin` is used.
    Serializer with lower priority will be created firstly
    """
    def __init__(self, *args, **kwargs):
        self._save_priority = kwargs.pop('priority', 0)
        super(SavePriorityMixin, self).__init__(*args, **kwargs)


class BaseNestedModelSerializer(serializers.ModelSerializer):
    def __init__(self, *args, **kwargs):
        # TODO: Find better solution for this
        # Copy ignore creation for future manipulations
        self._ignore_creation = copy(getattr(self.Meta, 'ignore_creation', ()))
        super(BaseNestedModelSerializer, self).__init__(*args, **kwargs)

    @staticmethod
    def get_sorted_by_save_priority(items):
        # Sort items by priority param if `PriorityMixin` is used
        return OrderedDict(
            sorted(
                items.items(),
                key=lambda item: getattr(item[1], '_save_priority', 0)
            )
        )

    def _get_related_field(self, field):
        model_class = self.Meta.model

        related_field = model_class._meta.get_field(field.source)
        if isinstance(related_field, ForeignObjectRel):
            return related_field.field, False
        return related_field, True

    def _get_new_serializer(self, serializer, **kwargs):
        kwargs.update({
            'context': self.context
        })
        return serializer.__class__(**kwargs)

    def call_after_saved_callback(self, field_name, instance=None):
        method = getattr(self, 'after_{}_saved'.format(field_name), None)
        if callable(method):
            method(instance)

    def after_reverse_relations_saved(self, instance):
        pass


class NestedCreateMixin(BaseNestedModelSerializer):
    """
    Mixin adds nested create feature.
    If you want to ignore creation of some fields use Meta param
    `ignore_creation` with tuple of field names, that will be skipped
    """
    def create(self, validated_data):
        reverse_relations = OrderedDict()
        relations = OrderedDict()

        # Sort fields by save priority
        fields = self.get_sorted_by_save_priority(self.fields)
        # Remove related fields from validated data for future manipulations
        for field_name, field in fields.items():
            if field.read_only or field_name in self._ignore_creation:
                continue
            related_field, direct = self._get_related_field(field)

            if isinstance(field, serializers.ListSerializer) and \
                    isinstance(field.child, serializers.ModelSerializer):
                if field.source not in validated_data or \
                        validated_data.get(field.source) is None:
                    # Skip field if field is not required or is null
                    continue

                validated_data.pop(field.source)

                reverse_relations[field_name] = (related_field, field.child)

            if isinstance(field, serializers.ModelSerializer):
                if field.source not in validated_data or \
                        validated_data.get(field.source) is None:
                    # Skip field if field is not required or is null
                    continue

                validated_data.pop(field.source)

                # Reversed one-to-one looks like direct foreign keys but they
                # are reverse relations
                if direct:
                    relations[field_name] = field
                else:
                    reverse_relations[field_name] = (related_field, field)

        # Create direct relations (foreign key, one-to-one)
        for field_name, field in relations.items():
            serializer = self._get_new_serializer(
                field, data=self.initial_data[field_name])
            serializer.is_valid(raise_exception=True)
            validated_data[field.source] = serializer.save()
            self.call_after_saved_callback(field_name)

        # Create instance
        instance = super(NestedCreateMixin, self).create(validated_data)

        if reverse_relations:
            self.create_reverse_relations(instance, reverse_relations)

        return instance

    def create_reverse_relations(self, instance, reverse_relations):
        # Create reverse relations
        # many-to-one, many-to-many, reversed one-to-one
        for field_name, (related_field, field) in reverse_relations.items():
            if related_field.many_to_many:
                save_kwargs = {}
            else:
                save_kwargs = {related_field.name: instance}

            related_data = self.initial_data[field_name]
            # Expand to array of one item for one-to-one for uniformity
            if related_field.one_to_one:
                related_data = [related_data]

            # Create related instances
            new_related_instances = []
            for data in related_data:
                serializer = self._get_new_serializer(field, data=data)
                serializer.is_valid(raise_exception=True)
                related_instance = serializer.save(**save_kwargs)
                new_related_instances.append(related_instance)

            if related_field.many_to_many:
                # Add m2m instances to through model via add
                m2m_manager = getattr(instance, field_name)
                m2m_manager.add(*new_related_instances)

            self.call_after_saved_callback(field_name, instance)
        self.after_reverse_relations_saved(instance)


class NestedUpdateMixin(BaseNestedModelSerializer):
    """
    Important notice: m2m relations are implemented as reverse foreign keys.
    It means serializer creates new instance for relation and deletes instance
    when relation is not given
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
                d.get('pk') for d in related_data if d.get('pk', None)
            ]
        )
        instances = {
            related_instance.pk: related_instance
            for related_instance in instances
        }
        return instances

    def update(self, instance, validated_data):
        reverse_relations = OrderedDict()
        relations = OrderedDict()

        # Sort fields by save priority
        fields = self.get_sorted_by_save_priority(self.fields)
        # Remove related fields from validated data for future manipulations
        for field_name, field in fields.items():
            if field.read_only:
                continue
            related_field, direct = self._get_related_field(field)

            if isinstance(field, serializers.ListSerializer):
                if isinstance(field.child, serializers.ModelSerializer):
                    if field.source not in validated_data or \
                            validated_data.get(field.source) is None:
                        # Skip field if field is not required or is null
                        continue

                    validated_data.pop(field.source)

                    reverse_relations[field_name] = (related_field, field.child)

            if isinstance(field, serializers.ModelSerializer):
                if field.source not in validated_data or \
                        validated_data.get(field.source) is None:
                    # Skip field if field is not required or is null
                    continue

                validated_data.pop(field.source)

                # Reversed one-to-one looks like direct foreign keys but they
                # are reverse relations
                if  direct:
                    relations[field_name] = field
                else:
                    reverse_relations[field_name] = (related_field, field)

        # Create or update direct relations (foreign key, one-to-one)
        if relations:
            for field_name, field in relations.items():
                model_class = field.Meta.model
                obj = model_class.objects.filter(
                    pk=self.initial_data[field_name].get('pk')).first()
                if obj:
                    serializer = self._get_new_serializer(
                        field, instance=obj,
                        data=self.initial_data[field_name])
                else:
                    serializer = self._get_new_serializer(
                        field, data=self.initial_data[field_name])
                serializer.is_valid(raise_exception=True)
                validated_data[field.source] = serializer.save()
                self.call_after_saved_callback(field_name, instance=instance)

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
                related_data = [related_data]

            instances = self.prefetch_related_instances(field, related_data)

            if related_field.many_to_many:
                save_kwargs = {}
            else:
                save_kwargs = {related_field.name: instance}

            new_related_instances = []
            for data in related_data:
                is_new = data.get('pk') is None
                if is_new:
                    serializer = self._get_new_serializer(field, data=data)
                else:
                    pk = data.get('pk')
                    obj = instances[pk]
                    serializer = self._get_new_serializer(
                        field, instance=obj, data=data)

                serializer.is_valid(raise_exception=True)
                related_instance = serializer.save(**save_kwargs)
                if is_new:
                    data['pk'] = related_instance.pk
                    new_related_instances.append(related_instance)

            if related_field.many_to_many:
                # Add m2m instances to through model via add
                m2m_manager = getattr(instance, field_name)
                m2m_manager.add(*new_related_instances)

            self.call_after_saved_callback(field_name, instance)
        self.after_reverse_relations_saved(instance)

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
                related_field_name =  related_field.rel.name
            else:
                related_field_name = related_field.name

            current_ids = [d.get('pk') for d in related_data]
            try:
                pks_to_delete = list(
                    model_class.objects.filter(
                        **{related_field_name: instance}
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
