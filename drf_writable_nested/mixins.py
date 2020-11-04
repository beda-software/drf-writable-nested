# -*- coding: utf-8 -*-
from collections import OrderedDict, defaultdict, Mapping
from urllib.parse import urlparse, unquote

from django.contrib.contenttypes.fields import GenericRelation
from django.contrib.contenttypes.models import ContentType
from django.db.models import ProtectedError
from django.db.models.fields.related import ForeignObjectRel
from django.db.utils import IntegrityError
from django.urls import Resolver404, resolve
from django.utils.translation import ugettext_lazy as _
from rest_framework import serializers
from rest_framework.exceptions import ValidationError
from rest_framework.fields import set_value, SkipField, get_error_detail
from django.core.exceptions import FieldDoesNotExist, ValidationError as DjangoValidationError, ObjectDoesNotExist
from rest_framework.settings import api_settings


class BaseNestedModelSerializer(serializers.ModelSerializer):

    def get_unique_together_validators(self):
        """Unique together validator needs to be disabled for Nested mixins to work properly."""
        return []

    def to_internal_value(self, data):
        """
        Dict of native values <- Dict of primitive datatypes.
        """
        if not isinstance(data, Mapping):
            message = self.error_messages['invalid'].format(
                datatype=type(data).__name__
            )
            raise ValidationError({
                api_settings.NON_FIELD_ERRORS_KEY: [message]
            }, code='invalid')

        ret = OrderedDict()
        errors = OrderedDict()
        fields = self._writable_fields

        for field in fields:
            validate_method = getattr(self, 'validate_' + field.field_name, None)
            primitive_value = field.get_value(data)

            if isinstance(primitive_value, str) and isinstance(field, serializers.HyperlinkedRelatedField):
                # we need this because DRF HyperlinkedRelatedField is not fully compatible with Django 2.0+
                # when dealing with spaces in the URL (e.g. when we do lookup by name).
                # The issue has been reported and reopened, see the description here:
                # - https://github.com/encode/django-rest-framework/issues/4748
                # Once it is resolved there, we won't need this line anymore
                primitive_value = unquote(primitive_value)

            try:
                # For create only
                if not self.partial and hasattr(self, 'initial_data') and isinstance(primitive_value, dict) \
                        and 'url' in primitive_value:
                    model_class = field.Meta.model
                    pk = self._get_related_pk(primitive_value, model_class, related_field=field)
                    if pk:
                        obj = model_class.objects.filter(
                            pk=pk,
                        ).first()
                        serializer = self._get_serializer_for_field(
                            field,
                            instance=obj,
                        )
                        primitive_value = {k: v for k, v in serializer.data.items()}
                        self.initial_data[field.field_name] = primitive_value
                validated_value = field.run_validation(primitive_value)
                if validate_method is not None:
                    validated_value = validate_method(validated_value)
            except ValidationError as exc:
                errors[field.field_name] = exc.detail
            except DjangoValidationError as exc:
                errors[field.field_name] = get_error_detail(exc)
            except SkipField:
                pass
            else:
                set_value(ret, field.source_attrs, validated_value)

        if errors:
            raise ValidationError(errors)

        return ret

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

                if direct and field.source not in self.initial_data:
                    # Field wasn't in the initial payload, likely a nested serializer with a default value
                    continue

                if direct and validated_data.get(field.source) is None:
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
            pk = self._get_related_pk(d, model_class, related_field=field)
            if pk:
                pk_list.append(pk)

        instances = {
            str(related_instance.pk): related_instance
            for related_instance in model_class.objects.filter(
                pk__in=pk_list
            )
        }

        return instances

    def _get_related_queryset(self, model_class, related_field):
        """
        Return a queryset of related instances with respect to custom list_serializer_class.

        If custom list_serializer_class has a filter_queryset method defined, it will be used
        to filter a set of related instances. Otherwise, all related instances will be
        returned by default.

        :param model_class: a class of related model
        :param related_field: a DRF field or seriaizer pointing to the related objects
        """
        queryset = model_class.objects.all()

        list_serializer_class = getattr(related_field.Meta, 'list_serializer_class', None)
        if list_serializer_class and hasattr(list_serializer_class, 'filter_queryset'):
            queryset = list_serializer_class.filter_queryset(queryset=queryset)

        return queryset

    def _get_related_pk(self, data, model_class, related_field=None):
        """
        Returns a PK of the related instance mentioned in the payload.

        Supports HyperlinkedIdentityField, UUIDFields, id and pk as resource identifiers.

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

            id_value = unquote(match.kwargs[lookup_field_name])

        # getting the actual instance
        queryset = self._get_related_queryset(model_class, related_field)
        try:
            instance = queryset.get(**{lookup_field_name: id_value})
        except ObjectDoesNotExist:
            instance = None

        if instance:
            return str(instance.pk)

    @staticmethod
    def _create_m2m_relations(m2m_model_class, instance_a, instance_b):
        """
        Creates a M2M relationship between two instances via M2M proxy model.

        If a certain relation already exists, does nothing.
        """
        # looking for FK field pointing to instance class
        params = {}

        # determine FK fields of m2m model
        fk_fields = [f for f in m2m_model_class._meta.fields if f.many_to_one]

        # assigning instances A and B to appropriate FK fields of m2m model
        for fk_field in fk_fields:

            if isinstance(instance_a, fk_field.related_model):
                params[fk_field.name] = instance_a

            elif isinstance(instance_b, fk_field.related_model):
                params[fk_field.name] = instance_b

        return m2m_model_class.objects.get_or_create(**params)

    @staticmethod
    def _remove_m2m_relations(m2m_model_class, instance_a, instance_b_class, pks_to_unlink):
        """
        Removes M2M relationship between instance A and specified instances B.
        """
        lookup_params = {}

        # determine FK fields of m2m model
        fk_fields = [f for f in m2m_model_class._meta.fields if f.many_to_one]

        for fk_field in fk_fields:

            if isinstance(instance_a, fk_field.related_model):
                lookup_params[fk_field.name] = instance_a

            if issubclass(instance_b_class, fk_field.related_model):
                lookup_params['{}__pk__in'.format(fk_field.name)] = pks_to_unlink

        # remove the relations
        assert len(lookup_params) > 1, "Lookup parameters to delete m2m relations are not fully set"
        return m2m_model_class.objects.filter(**lookup_params).delete()

    def update_or_create_reverse_relations(self, instance, reverse_relations):
        # Update or create reverse relations:
        # many-to-one, many-to-many, reversed one-to-one
        for field_name, (related_field, field, field_source) in \
                reverse_relations.items():

            # Skip processing for empty data or not-specified field.
            # The field can be defined in validated_data but isn't defined
            # in initial_data (for example, if multipart form data used)
            related_data = self.initial_data.get(field_name, None)
            if related_data is None:
                continue

            # Expand to array of one item for one-to-one for uniformity
            if related_field.one_to_one:
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
                    self._get_related_pk(data, field.Meta.model, related_field=field)
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

            # We check if the field was declared as a serializer for the through model.
            # We only need to create new relations if it wasn't.
            if related_field.many_to_many and field.Meta.model != related_field.remote_field.through:
                # add() method is not used here for adding M2M instances
                # because it doesn't support custom M2M proxy models
                m2m_model_class = related_field.remote_field.through

                for new_related_instance in new_related_instances:
                    self._create_m2m_relations(m2m_model_class, instance, new_related_instance)

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
            "protected relation exists"),
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

        # unlink or delete instances which are missed in payload
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
                    related_field.remote_field.name: instance,
                }
            elif isinstance(related_field, GenericRelation):
                related_field_lookup = \
                    self._get_generic_lookup(instance, related_field)
            else:
                related_field_lookup = {
                    related_field.name: instance,
                }

            # it's safe to use 'pk' here as it was pre-added by
            # update_or_create_reverse_relations method explicitly
            payload_ids = [d.get('pk') for d in related_data if d is not None]

            queryset = self._get_related_queryset(model_class, field)
            pks_to_unlink = list(
                queryset.filter(**related_field_lookup).exclude(
                    pk__in=payload_ids
                ).values_list('pk', flat=True)
            )

            if not pks_to_unlink:
                continue

            try:

                if related_field.many_to_many:
                    # Remove relations from m2m table.
                    m2m_model_class = related_field.remote_field.through
                    self._remove_m2m_relations(
                        m2m_model_class=m2m_model_class,
                        instance_a=instance,
                        instance_b_class=model_class,
                        pks_to_unlink=pks_to_unlink
                    )

                    if field_name in getattr(self.Meta, 'allow_delete_on_update', []):
                        # serializer is configured to delete related instances after unlinking
                        model_class.objects.filter(pk__in=pks_to_unlink).delete()

                elif field_name in getattr(self.Meta, 'allow_delete_on_update', []):
                    # serializer is configured to delete related instances after unlinking
                    model_class.objects.filter(pk__in=pks_to_unlink).delete()

                else:
                    # unlink related instances from parent instance
                    fields_to_null = {f: None for f in related_field_lookup.keys()}
                    model_class.objects.filter(pk__in=pks_to_unlink).update(**fields_to_null)

            except ProtectedError as e:
                instances = e.args[1]
                self.fail('cannot_delete_protected', instances=", ".join([
                    str(instance) for instance in instances]))

            except IntegrityError:
                raise Exception(f"Cannot unlink nested instances of '{field_name}' (related field '{related_field!r}', "
                                f"{pks_to_unlink}) from its parent instance '{instance!r}' because they have "
                                f"not-nullable keys to the parent. "
                                f"If this is a many-to-many relationship, consider adding '{field_name}' "
                                f"to Meta.allow_delete_on_update in the serializer.")
