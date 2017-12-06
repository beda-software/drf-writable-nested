# -*- coding: utf-8 -*-
import uuid
from collections import OrderedDict, defaultdict

from django.contrib.contenttypes.fields import GenericRelation
from django.contrib.contenttypes.models import ContentType
from django.utils.six.moves.urllib.parse import urlparse
from django.db.models import ProtectedError, FieldDoesNotExist
from django.db.models.fields.related import ForeignObjectRel
from django.utils.translation import ugettext_lazy as _
from rest_framework import serializers
from rest_framework.compat import resolve, Resolver404


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

                reverse_relations[field_name] = (
                    related_field, field.child, field.source)

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
                    relations[field_name] = (field, field.source)
                else:
                    reverse_relations[field_name] = (
                        related_field, field, field.source)

        return relations, reverse_relations

    def _get_related_field(self, field):
        model_class = self.Meta.model

        try:
            related_field = model_class._meta.get_field(field.source)
        except FieldDoesNotExist:
            # If `related_name` is not set, field name does not include `_set` -> remove it and check again
            default_postfix = '_set'
            if field.source.endswith(default_postfix):
                related_field = model_class._meta.get_field(field.source[:-len(default_postfix)])
            else:
                raise

        if isinstance(related_field, ForeignObjectRel):
            return related_field.field, False
        return related_field, True

    def _get_serializer_for_field(self, field, **kwargs):
        kwargs.update({
            'context': self.context,
            'partial': self.partial,
        })
        return field.__class__(**kwargs)

    def _get_generic_lookup(self, instance, related_field):
        return {
            related_field.content_type_field_name:
                ContentType.objects.get_for_model(instance),
            related_field.object_id_field_name: instance.pk,
        }

    def prefetch_related_instances(self, field, related_data):
        model_class = field.Meta.model
        pk_list = []
        for d in filter(None, related_data):
            pk = self._get_related_pk(d, model_class)
            if pk:
                pk_list.append(pk)

        instances = {
            str(related_instance.pk): related_instance
            for related_instance in model_class.objects.filter(
                pk__in=pk_list
            )
        }

        return instances

    def _get_related_pk(self, data, model_class, related_field=None):
        """
        Returns a PK of the related instance mentioned in the payload.

        :param data: a nested portion of the payload associated with the related field
        :param model_class: a related model class (can be computed out of related_field)
        :param related_field: a field which declares a nested serializer
        """

        if related_field is None:
            # fallback to default behavior
            return data.get('pk') or data.get(model_class._meta.pk.attname)

        # figuring out which fields of nested serializer might be used as ID
        id_types = (serializers.HyperlinkedIdentityField, serializers.UUIDField)
        id_names = ('pk', model_class._meta.pk.attname, 'id')

        possible_id_fields = {
            field_name: field_obj
            for field_name, field_obj in related_field.fields.fields.items()
            if isinstance(field_obj, id_types) or field_name in id_names
        }

        # looking for one of these fields in the payload
        try:
            id_field_name = (set(possible_id_fields) & set(data)).pop()
            id_field_obj = possible_id_fields[id_field_name]
            id_data = data[id_field_name]
        except KeyError:
            # payload doesn't have any data about id, return nothing
            return

        # retrieving an id value out of payload. For non hyperlinked fields
        # the id_data in the payload is an actual id we can use to lookup a related instance
        lookup_field_name = id_field_name
        id_value = id_data

        if isinstance(id_field_obj, serializers.HyperlinkedIdentityField):
            # in case of HyperlinkedIdentityField, id_data is an url pointing to instance,
            # so we need to retrieve an id out of it with respect to URLs scheme
            lookup_field_name = id_field_obj.lookup_field

            path = urlparse(id_data).path
            try:
                match = resolve(path)
            except Resolver404:
                return

            id_value = match.kwargs[lookup_field_name]

        # getting the actual instance. TODO: this is to be merged with outer code
        instance = model_class.objects.filter(**{lookup_field_name: id_value}).first()
        if instance:
            return str(instance.pk)


    def update_or_create_reverse_relations(self, instance, reverse_relations):
        # Update or create reverse relations:
        # many-to-one, many-to-many, reversed one-to-one
        for field_name, (related_field, field, field_source) in \
                reverse_relations.items():

            if self.partial and field_name not in self.initial_data:
                # in case of partial update, related fields don't have to be in the payload
                continue

            related_data = self.initial_data[field_name]
            # Expand to array of one item for one-to-one for uniformity
            if related_field.one_to_one:
                if related_data is None:
                    # Skip processing for empty data
                    continue
                related_data = [related_data]

            instances = self.prefetch_related_instances(field, related_data)

            save_kwargs = self.get_save_kwargs(field_name)
            if isinstance(related_field, GenericRelation):
                save_kwargs.update(
                    self._get_generic_lookup(instance, related_field),
                )
            elif not related_field.many_to_many:
                save_kwargs[related_field.name] = instance

            new_related_instances = []
            for data in related_data:
                obj = instances.get(
                    self._get_related_pk(data, field.Meta.model, related_field=related_field)
                )
                serializer = self._get_serializer_for_field(
                    field,
                    instance=obj,
                    data=data,
                )
                serializer.is_valid(raise_exception=True)
                related_instance = serializer.save(**save_kwargs)
                data['pk'] = related_instance.pk
                new_related_instances.append(related_instance)

            if related_field.many_to_many:
                # Add m2m instances to through model via add
                m2m_manager = getattr(instance, field_source)
                m2m_manager.add(*new_related_instances)

    def update_or_create_direct_relations(self, attrs, relations):
        for field_name, (field, field_source) in relations.items():
            obj = None

            if self.partial and field_name not in self.initial_data:
                # in case of partial update, related fields don't have to be in the payload
                continue

            data = self.initial_data[field_name]
            model_class = field.Meta.model
            pk = self._get_related_pk(data, model_class, related_field=field)
            if pk:
                obj = model_class.objects.filter(
                    pk=pk,
                ).first()
            serializer = self._get_serializer_for_field(
                field,
                instance=obj,
                data=data,
            )
            serializer.is_valid(raise_exception=True)
            attrs[field_source] = serializer.save(
                **self.get_save_kwargs(field_name)
            )

    def save(self, **kwargs):
        self.save_kwargs = defaultdict(dict, kwargs)

        return super(BaseNestedModelSerializer, self).save(**kwargs)

    def get_save_kwargs(self, field_name):
        save_kwargs = self.save_kwargs[field_name]
        if not isinstance(save_kwargs, dict):
            raise TypeError(
                _("Arguments to nested serializer's `save` must be dict's")
            )

        return save_kwargs


class NestedCreateMixin(BaseNestedModelSerializer):
    """
    Mixin adds nested create feature
    """
    def create(self, validated_data):
        relations, reverse_relations = self._extract_relations(validated_data)

        # Create or update direct relations (foreign key, one-to-one)
        self.update_or_create_direct_relations(
            validated_data,
            relations,
        )

        # Create instance
        instance = super(NestedCreateMixin, self).create(validated_data)

        self.update_or_create_reverse_relations(instance, reverse_relations)

        return instance


class NestedUpdateMixin(BaseNestedModelSerializer):
    """
    Mixin adds update nested feature
    """
    default_error_messages = {
        'cannot_delete_protected': _(
            "Cannot delete {instances} because "
            "protected relation exists")
    }

    def update(self, instance, validated_data):
        relations, reverse_relations = self._extract_relations(validated_data)

        # Create or update direct relations (foreign key, one-to-one)
        self.update_or_create_direct_relations(
            validated_data,
            relations,
        )

        # Update instance
        instance = instance._meta.model.objects.get(pk=instance.pk)
        instance = super(NestedUpdateMixin, self).update(
            instance,
            validated_data,
        )
        self.update_or_create_reverse_relations(instance, reverse_relations)
        self.delete_reverse_relations_if_need(instance, reverse_relations)
        return instance

    def delete_reverse_relations_if_need(self, instance, reverse_relations):
        # Reverse `reverse_relations` for correct delete priority
        reverse_relations = OrderedDict(
            reversed(list(reverse_relations.items())))

        # Delete instances which is missed in data
        for field_name, (related_field, field, field_source) in \
                reverse_relations.items():
            model_class = field.Meta.model

            related_data = self.initial_data[field_name]
            # Expand to array of one item for one-to-one for uniformity
            if related_field.one_to_one:
                related_data = [related_data]

            # M2M relation can be as direct or as reverse. For direct relation we
            # should use reverse relation name
            if related_field.many_to_many and \
                    not isinstance(related_field, ForeignObjectRel):
                related_field_lookup = {
                    related_field.rel.name: instance,
                }
            elif isinstance(related_field, GenericRelation):
                related_field_lookup = \
                    self._get_generic_lookup(instance, related_field)
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
                    # Remove relations from m2m table
                    m2m_manager = getattr(instance, field_source)
                    m2m_manager.remove(*pks_to_delete)
                else:
                    model_class.objects.filter(pk__in=pks_to_delete).delete()

            except ProtectedError as e:
                instances = e.args[1]
                self.fail('cannot_delete_protected', instances=", ".join([
                    str(instance) for instance in instances]))
