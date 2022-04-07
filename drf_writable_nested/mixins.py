# -*- coding: utf-8 -*-
import logging
from collections import OrderedDict, defaultdict
from typing import List, Tuple

from django.contrib.contenttypes.fields import GenericRelation
from django.contrib.contenttypes.models import ContentType
from django.core.exceptions import FieldDoesNotExist, ObjectDoesNotExist
from django.db import transaction, router, IntegrityError
from django.db.models import OneToOneRel, ProtectedError
from django.db.models.fields.related import ForeignObjectRel, ManyToManyField
from django.utils.translation import gettext_lazy as _
from rest_framework import serializers
from rest_framework.exceptions import ValidationError
from rest_framework.fields import empty
from rest_framework.relations import ManyRelatedField
from rest_framework.serializers import BaseSerializer, ListSerializer
from rest_framework.validators import UniqueValidator, UniqueTogetherValidator

# permit writable nested serializers
serializers.raise_errors_on_nested_writes = lambda a, b, c: None


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
            # If `related_name` is not set, field name does not include
            # `_set` -> remove it and check again
            default_postfix = '_set'
            if field.source.endswith(default_postfix):
                related_field = model_class._meta.get_field(
                    field.source[:-len(default_postfix)])
            else:
                raise

        if isinstance(related_field, ForeignObjectRel):
            return related_field.field, False
        return related_field, True

    def _get_serializer_for_field(self, field, **kwargs):
        kwargs.update({
            'context': self.context,
            'partial': self.partial if kwargs.get('instance') else False,
        })

        # if field is a polymorphic serializer
        if hasattr(field, '_get_serializer_from_resource_type'):
            # get 'real' serializer based on resource type
            serializer = field._get_serializer_from_resource_type(
                kwargs.get('data').get(field.resource_type_field_name)
            )

            return serializer.__class__(**kwargs)
        else:
            return field.__class__(**kwargs)

    def _get_generic_lookup(self, instance, related_field):
        return {
            related_field.content_type_field_name:
                ContentType.objects.get_for_model(instance),
            related_field.object_id_field_name: instance.pk,
        }

    def _get_related_pk(self, data, model_class):
        pk = data.get('pk') or data.get(model_class._meta.pk.attname)

        if pk:
            return str(pk)

        return None

    def _extract_related_pks(self, field, related_data):
        model_class = field.Meta.model
        pk_list = []
        for d in filter(None, related_data):
            pk = self._get_related_pk(d, model_class)
            if pk:
                pk_list.append(pk)

        return pk_list

    def _prefetch_related_instances(self, field, related_data):
        model_class = field.Meta.model
        pk_list = self._extract_related_pks(field, related_data)

        instances = {
            str(related_instance.pk): related_instance
            for related_instance in model_class.objects.filter(
                pk__in=pk_list
            )
        }

        return instances

    def update_or_create_reverse_relations(self, instance, reverse_relations):
        # Update or create reverse relations:
        # many-to-one, many-to-many, reversed one-to-one
        for field_name, (related_field, field, field_source) in \
                reverse_relations.items():

            # Skip processing for empty data or not-specified field.
            # The field can be defined in validated_data but isn't defined
            # in initial_data (for example, if multipart form data used)
            related_data = self.get_initial().get(field_name, None)
            if related_data is None:
                continue

            if related_field.one_to_one:
                # If an object already exists, fill in the pk so
                # we don't try to duplicate it
                pk_name = field.Meta.model._meta.pk.attname
                if pk_name not in related_data and 'pk' in related_data:
                    pk_name = 'pk'
                if pk_name not in related_data:
                    related_instance = getattr(instance, field_source, None)
                    if related_instance:
                        related_data[pk_name] = related_instance.pk

                # Expand to array of one item for one-to-one for uniformity
                related_data = [related_data]

            instances = self._prefetch_related_instances(field, related_data)

            save_kwargs = self._get_save_kwargs(field_name)
            if isinstance(related_field, GenericRelation):
                save_kwargs.update(
                    self._get_generic_lookup(instance, related_field),
                )
            elif not related_field.many_to_many:
                save_kwargs[related_field.name] = instance

            new_related_instances = []
            errors = []
            for data in related_data:
                obj = instances.get(
                    self._get_related_pk(data, field.Meta.model)
                )
                serializer = self._get_serializer_for_field(
                    field,
                    instance=obj,
                    data=data,
                )
                try:
                    serializer.is_valid(raise_exception=True)
                    related_instance = serializer.save(**save_kwargs)
                    data['pk'] = related_instance.pk
                    new_related_instances.append(related_instance)
                    errors.append({})
                except ValidationError as exc:
                    errors.append(exc.detail)

            if any(errors):
                if related_field.one_to_one:
                    raise ValidationError({field_name: errors[0]})
                else:
                    raise ValidationError({field_name: errors})

            if related_field.many_to_many:
                # Add m2m instances to through model via add
                m2m_manager = getattr(instance, field_source)
                m2m_manager.add(*new_related_instances)

    def update_or_create_direct_relations(self, attrs, relations):
        for field_name, (field, field_source) in relations.items():
            obj = None
            data = self.get_initial()[field_name]
            model_class = field.Meta.model
            pk = self._get_related_pk(data, model_class)
            if pk:
                obj = model_class.objects.filter(
                    pk=pk,
                ).first()
            serializer = self._get_serializer_for_field(
                field,
                instance=obj,
                data=data,
            )

            try:
                serializer.is_valid(raise_exception=True)
                attrs[field_source] = serializer.save(
                    **self._get_save_kwargs(field_name)
                )
            except ValidationError as exc:
                raise ValidationError({field_name: exc.detail})

    def save(self, **kwargs):
        self._save_kwargs = defaultdict(dict, kwargs)

        return super(BaseNestedModelSerializer, self).save(**kwargs)

    def _get_save_kwargs(self, field_name):
        save_kwargs = self._save_kwargs[field_name]
        if not isinstance(save_kwargs, dict):
            raise TypeError(
                _("Arguments to nested serializer's `save` must be dict's")
            )

        return save_kwargs


class NestedCreateMixin(BaseNestedModelSerializer):
    """
    Adds nested create feature
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
    Adds update nested feature
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
        instance = super(NestedUpdateMixin, self).update(
            instance,
            validated_data,
        )
        self.update_or_create_reverse_relations(instance, reverse_relations)
        self.delete_reverse_relations_if_need(instance, reverse_relations)
        instance.refresh_from_db()
        return instance

    def perform_nested_delete(self, pks_to_delete, model_class, instance, related_field, field_source):
        if related_field.many_to_many:
            # Remove relations from m2m table
            m2m_manager = getattr(instance, field_source)
            m2m_manager.remove(*pks_to_delete)
        else:
            model_class.objects.filter(pk__in=pks_to_delete).delete()

    def delete_reverse_relations_if_need(self, instance, reverse_relations):
        # Reverse `reverse_relations` for correct delete priority
        reverse_relations = OrderedDict(
            reversed(list(reverse_relations.items())))

        # Delete instances which is missed in data
        for field_name, (related_field, field, field_source) in \
                reverse_relations.items():
            model_class = field.Meta.model

            related_data = self.get_initial()[field_name]
            # Expand to array of one item for one-to-one for uniformity
            if related_field.one_to_one:
                related_data = [related_data]

            # M2M relation can be as direct or as reverse. For direct relation
            # we should use reverse relation name
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

            current_ids = self._extract_related_pks(field, related_data)

            try:
                pks_to_delete = list(
                    model_class.objects.filter(
                        **related_field_lookup
                    ).exclude(
                        pk__in=current_ids
                    ).values_list('pk', flat=True)
                )
                self.perform_nested_delete(pks_to_delete, model_class, instance, related_field, field_source)

            except ProtectedError as e:
                instances = e.args[1]
                self.fail('cannot_delete_protected', instances=", ".join([
                    str(instance) for instance in instances]))


class UniqueFieldsMixin(serializers.ModelSerializer):
    """
    Moves `UniqueValidator`'s from the validation stage to the save stage.
    It solves the problem with nested validation for unique fields on update.

    If you want more details, you can read related issues and articles:
    https://github.com/beda-software/drf-writable-nested/issues/1
    http://www.django-rest-framework.org/api-guide/validators/#updating-nested-serializers

    Example of usage:
    ```
        class Child(models.Model):
        field = models.CharField(unique=True)


    class Parent(models.Model):
        child = models.ForeignKey('Child')


    class ChildSerializer(UniqueFieldsMixin, serializers.ModelSerializer):
        class Meta:
            model = Child


    class ParentSerializer(NestedUpdateMixin, serializers.ModelSerializer):
        child = ChildSerializer()

        class Meta:
            model = Parent
    ```

    Note: `UniqueFieldsMixin` must be applied only on the serializer
    which has unique fields.

    Note: When you are using both mixins
    (`UniqueFieldsMixin` and `NestedCreateMixin` or `NestedUpdateMixin`)
    you should put `UniqueFieldsMixin` ahead.
    """
    _unique_fields = []  # type: List[Tuple[str,UniqueValidator]]

    def get_fields(self):
        self._unique_fields = []

        fields = super(UniqueFieldsMixin, self).get_fields()
        for field_name, field in fields.items():
            unique_validators = [validator
                                 for validator in field.validators
                                 if isinstance(validator, UniqueValidator)]
            if unique_validators:
                # 0 means only take the first one UniqueValidator
                self._unique_fields.append((field_name, unique_validators[0]))
                field.validators = [
                    validator for validator in field.validators
                    if not isinstance(validator, UniqueValidator)]

        return fields

    def _validate_unique_fields(self, validated_data):
        for unique_field in self._unique_fields:
            field_name, unique_validator = unique_field
            if self.partial and field_name not in validated_data:
                continue
            try:
                # `set_context` removed on DRF >= 3.11, pass in via __call__ instead
                if hasattr(unique_validator, 'set_context'):
                    unique_validator.set_context(self.fields[field_name])
                    unique_validator(validated_data[field_name])
                else:
                    unique_validator(validated_data[field_name],
                                     self.fields[field_name])
            except ValidationError as exc:
                raise ValidationError({field_name: exc.detail})

    def create(self, validated_data):
        self._validate_unique_fields(validated_data)
        return super(UniqueFieldsMixin, self).create(validated_data)

    def update(self, instance, validated_data):
        self._validate_unique_fields(validated_data)
        return super(UniqueFieldsMixin, self).update(instance, validated_data)


class FieldLookupMixin(serializers.Serializer):

    def __init__(self, *args, **kwargs):
        self.logger = logging.getLogger(self.__class__.__name__)
        super(FieldLookupMixin, self).__init__(*args, **kwargs)

    def _get_model_field(self, source):
        """Returns the field on the model"""
        # for serializers like ModelSerializer, the Meta.model can be used to classify fields
        if not hasattr(self, 'Meta') or not hasattr(self.Meta, 'model'):
            return None
        try:
            return self.Meta.model._meta.get_field(source)
        except FieldDoesNotExist:
            pass
        try:
            # If `related_name` is not set, field name does not include
            # `_set` -> remove it and check again
            default_postfix = '_set'
            if source.endswith(default_postfix):
                return self.Meta.model._meta.get_field(source[:-len(default_postfix)])
        except FieldDoesNotExist:
            pass
        return None

    TYPE_READ_ONLY = 'read-only'
    TYPE_LOCAL = 'local'
    TYPE_DIRECT = 'direct'
    TYPE_REVERSE = 'reverse'

    _cache_field_types = None
    _cache_field_sources = None

    @property
    def field_sources(self):
        if self._cache_field_sources is None:
            self._populate_field_types()
        return self._cache_field_sources

    @property
    def field_types(self):
        if self._cache_field_types is None:
            self._populate_field_types()
        return self._cache_field_types

    def _populate_field_types(self):
        self._cache_field_types = {}
        self._cache_field_sources = {}
        for field_name, field in self.fields.items():
            if isinstance(self._get_model_field(field.source), GenericRelation):
                raise TypeError("GenericRelation not currently supported")
            if field.read_only:
                self._cache_field_types[field_name] = self.TYPE_READ_ONLY
                self._cache_field_sources[field.source] = self.TYPE_READ_ONLY
                continue
            if not isinstance(field, BaseSerializer):
                self._cache_field_types[field_name] = self.TYPE_LOCAL
                self._cache_field_sources[field.source] = self.TYPE_LOCAL
                continue
            if field.source == '*':
                self._cache_field_types[field_name] = self.TYPE_DIRECT
                continue
            model_field = self._get_model_field(field.source)
            if isinstance(model_field, OneToOneRel):
                self._cache_field_types[field_name] = self.TYPE_REVERSE
                self._cache_field_sources[field.source] = self.TYPE_REVERSE
                # TODO continue?
            if isinstance(model_field, ForeignObjectRel):
                self._cache_field_types[field_name] = self.TYPE_REVERSE
                self._cache_field_sources[field.source] = self.TYPE_REVERSE
                continue
            self._cache_field_types[field_name] = self.TYPE_DIRECT
            self._cache_field_sources[field.source] = self.TYPE_DIRECT


class RelatedSaveMixin(FieldLookupMixin):
    """
    RelatedSaveMixin handes the saving of nested fields, both direct and reverse relations:
     - Direct relations needs to be saved first
     - The focal object can then be saved (which ensures the focal PK is available)
     - Finally, reverse relations can be udpated with the object PK
    """
    _is_saved = False

    def run_validation(self, data=empty):
        """Cache nested call to `to_representation` on _validate_data for use when saving."""
        self.logger.debug("{} validating: {}".format(self.__class__.__name__, data))
        self._validated_data = super(RelatedSaveMixin, self).run_validation(data)
        self.logger.debug("{} validated: {}".format(self.__class__.__name__, self._validated_data))
        self._errors = {}
        return self._validated_data

    def to_internal_value(self, data):
        """Injects the PK of this field into reverse relations so they validate when created in to_internal_value."""
        self._make_reverse_relations_valid()
        return super(RelatedSaveMixin, self).to_internal_value(data)

    def _make_reverse_relations_valid(self):
        """Make the reverse ForeignKey field optional since we may not have a key for the base object yet."""
        for field_name, field in self.fields.items():
            if self.field_types[field_name] != self.TYPE_REVERSE:
                continue
            # we know this is a reverse so reverse_field.field is valid
            related_field = self._get_model_field(field.source).field
            if isinstance(field, serializers.ListSerializer):
                field = field.child
            # find the serializer field matching the reverse model relation
            for sub_field in field.fields.values():
                if sub_field.source == related_field.name:
                    sub_field.required = False
                    # found the matching field, move on
                    break

    @property
    def validated_data(self):
        """If mixed into a standard Serializer, prevents `save` from accessing reverse relations"""
        return {k: v for k, v in super(RelatedSaveMixin, self).validated_data.items()
                if k not in self.field_sources or self.field_sources[k] != self.TYPE_REVERSE}

    def save(self, **kwargs):
        """Convert validated data into related objects and save."""
        # Create or update direct relations (foreign key, one-to-one)
        self.logger.debug("RelatedSaveMixin.save for {} with data, kwargs: {}, {}".format(self.__class__.__name__, self._validated_data, kwargs))
        self._save_direct_relations(kwargs=kwargs)
        instance = super(RelatedSaveMixin, self).save(**kwargs)
        if instance is None:  # possibly with GetOnly or UpdateOnly
            # cannot create reverse relations with no object
            return None
        self._save_reverse_relations(instance=instance, kwargs=kwargs)
        return instance

    def _save_direct_relations(self, kwargs):
        """Save direct relations so FKs exist when committing the base instance"""
        if self._validated_data is None and kwargs == {}:
            return  # delete-only
        for field_name, field in self.fields.items():
            if self.field_types[field_name] != self.TYPE_DIRECT:
                continue
            self.logger.debug("{} direct save {} with data, kwargs;  {}, {}".format(self.__class__.__name__, field_name, self._validated_data.get(field.source, empty), kwargs.get(field_name, {})))
            if self._validated_data.get(field.source, empty) == empty and kwargs.get(field_name, empty) == empty:
                continue  # nothing to save
            #if self._validated_data.get(field_name) is None or kwargs.get(field_name) is None:
            #    continue  # delete existing objects
            # we need to pop from kwargs so the value doesn't "overwrite" the value generated by save
            self._validated_data[field.source] = field.save(**kwargs.pop(field_name, {}))
            self.logger.debug("{}._validated_data[{}] set to direct {}".format(self.__class__.__name__, field_name, self._validated_data[field.source]))

    def _format_generic_lookup(self, instance, related_field):
        return {
            related_field.content_type_field_name: ContentType.objects.get_for_model(instance),
            related_field.object_id_field_name: instance.pk,
        }

    def _save_reverse_relations(self, instance, kwargs):
        """Inject the current object as the FK in the reverse related objects and save them"""
        for field_name, field in self.fields.items():
            if self.field_types[field_name] != self.TYPE_REVERSE:
                continue
            if self._validated_data is None and kwargs == {}:
                return  # delete-only
            if self._validated_data.get(field.source, empty) == empty and kwargs.get(field_name, empty) == empty:
                continue  # nothing to save
            model_field = self._get_model_field(field.source)
            self.logger.debug("{} populating reverse field {}".format(self.__class__.__name__, model_field.field.name))
            if isinstance(field, serializers.ListSerializer):
                # reverse FK, inject the instance into reverse relations so the <parent>_id FK field is valid when saved
                for obj in field._validated_data:
                    obj[model_field.field.name] = instance
            elif isinstance(field, serializers.ModelSerializer):
                # 1:1
                if self._validated_data[field.source] is None:
                    # indicates that we should delete 1:1 relation (if it exists)
                    try:
                        getattr(instance, field.source).delete()
                        continue
                    except ObjectDoesNotExist:
                        pass
                else:
                    field._validated_data[model_field.field.name] = instance
            else:
                raise Exception("unexpected serializer type")
            # create/update (as appropriate) related objects
            self._validated_data[field.source] = field.save(**kwargs.get(field_name, {}))
            self.logger.debug("{}._validated_data[{}] to reverse {}".format(self.__class__.__name__, field_name, self._validated_data[field.source]))

            # eliminate related objects that weren't in the request
            if isinstance(field, ListSerializer):
                # due to a bug in Django, calling `set` on a non-nullable reverse relation will only `add`
                if model_field.field.null:
                    getattr(instance, field.source).set(self._validated_data[field.source])
                else:
                    # models should be attached when saved so we only need to delete
                    obj_field = getattr(instance, field.source)
                    db = router.db_for_write(obj_field.model, instance=instance)
                    old_objs = set(obj_field.using(db).all())
                    for obj in old_objs:
                        if obj not in self._validated_data[field.source]:
                            obj.delete()


class FocalSaveMixin(FieldLookupMixin):
    """Provides a framework for extracting the values needed to get or create the focal object."""

    default_error_messages = {
        'incorrect_type': _('Nested field received an incorrect data type ({data_type}):  {exception_message}'),
    }

    def to_internal_value(self, data):
        """Injects the PK of this field into reverse relations so they validate when created in to_internal_value."""
        # to_internal_value only preserves writable fields and match_on may need read-only like PK
        self._validated_data = super(FocalSaveMixin, self).to_internal_value(data)
        # patch read-only fields for match_on
        for field_name, field in self.fields.items():
            if not field.read_only:
                continue
            if field_name not in data:
                continue
            try:
                self._validated_data[field.source] = field.to_internal_value(data[field_name])
            except NotImplementedError:
                pass  # if `to_internal_value` isn't provided, we won't be able to match on it
        return self._validated_data

    def build_match_on(self, kwargs):
        match_on = {}
        for field_name, field in self.fields.items():
            if self.match_on == '__all__' or field_name in self.match_on:
                # build match_on dict
                if hasattr(field, 'build_match_on'):
                    # create matching criteria
                    related_match_on = field.build_match_on(kwargs)
                    # apply match to nested field
                    match_on.update({"{}__{}".format(field.source, k): v for k, v in related_match_on.items()})
                else:
                    match_on[field.source] = kwargs.get(field_name, self._validated_data.get(field.source))
        # a parent serializer may inject a value that isn't among the fields, but is in `match_on`
        for key in self.match_on:
            if key not in self.fields.keys():
                match_on[key] = kwargs.get(key, None)
        return match_on

    def build_direct_values(self, kwargs):
        values = {}
        for field_name, field in self.fields.items():
            if isinstance(field, ManyRelatedField) or isinstance(self._get_model_field(field.source), ManyToManyField):
                continue  # m2m fields
            elif field.source == '*':
                continue
            elif self.field_types[field_name] == self.TYPE_LOCAL:
                # need to check kwargs dict since there's no pre-processing
                values[field.source] = kwargs.get(field_name, self._validated_data.get(field.source))
            elif self.field_types[field_name] == self.TYPE_DIRECT:
                # kwargs should have been injected into _validated_data when direct relations were saved
                values[field.source] = self._validated_data.get(field.source)
            # reverse relations aren't sent to a create
        return values

    def match(self, kwargs):
        self.logger.debug("FocalSaveMixin.match with no super and kwargs {}".format(kwargs))
        return self.instance, False

    @transaction.atomic
    def save(self, **kwargs):
        self.logger.debug("FocalSaveMixin.save for {} with data, kwargs {}".format(self.__class__.__name__, self._validated_data, kwargs))
        if self._validated_data is None and kwargs == {}:
            return None  # deleted
        match, needs_saved = self.match(kwargs)
        self.logger.debug("Match: {}".format(match))
        needs_saved = self.do_update(match, kwargs) or needs_saved
        try:
            if needs_saved:
                match.save()
        except (TypeError, ValueError) as e:
            self.fail('incorrect_type', data_type=type(self._validated_data).__name__, exception_message=e.args)
        self.do_m2m_update(match, kwargs)
        return match

    def do_update(self, match, create_values):
        """Update the match (if appropriate) and returns a boolean indicating whether or not a save is required."""
        return False

    def do_m2m_update(self, match, kwargs):
        return  # no update


class NestedSaveListSerializer(serializers.ListSerializer):
    """Need a special save() method that cascades to the list of child instances"""

    def __init__(self, *args, **kwargs):
        self.logger = logging.getLogger(self.__class__.__name__)
        super(NestedSaveListSerializer, self).__init__(*args, **kwargs)

    def save(self, **kwargs):
        """
        Save and return a list of object instances.
        """
        # Guard against incorrect use of `serializer.save(commit=False)`
        assert 'commit' not in kwargs, (
            "'commit' is not a valid keyword argument to the 'save()' method. "
            "If you need to access data before committing to the database then "
            "inspect 'serializer.validated_data' instead. "
            "You can also pass additional keyword arguments to 'save()' if you "
            "need to set extra attributes on the saved model instance. "
            "For example: 'serializer.save(owner=request.user)'.'"
        )
        self.logger.debug("List-{} save with data, kwargs: {}, {}".format(self.child.__class__.__name__, self._validated_data, kwargs))

        new_values = []

        for item in self._validated_data:
            # integrate save kwargs
            self.child._validated_data = item
            new_value = self.child.save(**kwargs)
            # None indicates a deleted item
            if new_value is not None:
                new_values.append(new_value)

        self.logger.debug("List-{} saved: {}".format(self.child.__class__.__name__, new_values))
        return new_values

    def run_validation(self, data=empty):
        """Since a nested serializer is treated like a Field, `is_valid` will not be called so we need to set
        _validated_data in the mixin."""
        self.logger.debug("List-{} validating: {}".format(self.child.__class__.__name__, data))
        self._validated_data = super(NestedSaveListSerializer, self).run_validation(data)
        self.logger.debug("List-{} validated: {}".format(self.child.__class__.__name__, self._validated_data))
        return self._validated_data

    def build_match_on(self, kwargs):
        matches = []
        for item in self._validated_data:
            self.child._validated_data = item
            match, needs_save = self.child.match(kwargs)
            if not needs_save:  # we retrieved an instance
                matches.append(match.pk)
        return {
            # TODO: make flexible e.g. to support match all
            'in': matches
        }


class NestedSaveSerializer(RelatedSaveMixin, FocalSaveMixin):
    """Provides a general framework for nested serializers including argument validation."""

    default_list_serializer = NestedSaveListSerializer
    DEFAULT_MATCH_ON = ['pk']
    queryset = None

    @classmethod
    def many_init(cls, *args, **kwargs):
        # inject the default into list_serializer_class (if not present)
        meta = getattr(cls, 'Meta', None)
        if meta is None:
            class Meta:
                pass
            meta = Meta
            setattr(cls, 'Meta', meta)
        list_serializer_class = getattr(meta, 'list_serializer_class', None)
        if list_serializer_class is None:
            setattr(meta, 'list_serializer_class', cls.default_list_serializer)
        assert issubclass(meta.list_serializer_class, NestedSaveListSerializer), \
            "NestedSaveMixin expects a NestedSaveListSerializer for correct save behavior.  Please override " \
            "default_list_serializer or Meta.list_serializer_class and provide an appropriate class."
        return super(NestedSaveSerializer, cls).many_init(*args, **kwargs)

    def __init__(self, *args, **kwargs):
        if kwargs.get('partial', False) is True:
            raise ValueError("Partial Updates not currently supported by NestedSaveSerializer")
        self.queryset = kwargs.pop('queryset', self.queryset)
        if self.queryset is None and hasattr(self, 'Meta') and hasattr(self.Meta, 'model'):
            self.queryset = self.Meta.model.objects.all()
        assert self.queryset is not None, \
            "NestedSerializerBase requires a Meta.model, a `queryset` on the Serializer, or a `queryset` kwarg"
        self.match_on = kwargs.pop('match_on', self.DEFAULT_MATCH_ON)
        assert self.match_on == '__all__' or isinstance(self.match_on, (tuple, list, set)), \
            "match_on only accepts as Collection of strings or the special value __all__"
        if isinstance(self.match_on, (tuple, list, set)):
            for match in self.match_on:
                assert isinstance(match, str), "match_on collection can only contain strings"
        super(NestedSaveSerializer, self).__init__(*args, **kwargs)

    def run_validation(self, data=empty):
        """A nested serializer is treated like a Field so `is_valid` will not be called and `_validated_data` not set."""
        self.logger.debug("{} validating: {}".format(self.__class__.__name__, data))
        # ensure Unique and UniqueTogether don't collide with a DB match
        validators = self.remove_validation_unique()
        self._validated_data = super(NestedSaveSerializer, self).run_validation(data)
        self.logger.debug("{} validated: {}".format(self.__class__.__name__, self._validated_data))
        # restore Unique or UniqueTogether
        self.restore_validation_unique(validators)
        return self._validated_data

    def remove_validation_unique(self):
        """
        Removes unique validators from a serializers.  This is critical for get-or-create style serialization.  It can also
        be used to distinguish 409 errors from client-side validation errors.
        """
        fields = {}
        # extract unique validators
        for field_name, field in self.fields.items():
            fields[field_name] = []
            if not hasattr(field, 'validators'):
                continue
            for validator in field.validators:
                if isinstance(validator, UniqueValidator):
                    fields[field_name].append(validator)
            for validator in fields[field_name]:
                field.validators.remove(validator)
        # extract unique_together validators
        fields['_'] = []
        for validator in self.validators:
            if isinstance(validator, UniqueTogetherValidator):
                fields['_'].append(validator)
        for validator in fields['_']:
            self.validators.remove(validator)
        return fields

    def restore_validation_unique(self, unique_validators):
        together_validators = unique_validators.pop('_')
        for serializer in together_validators:
            self.validators.append(serializer)
        fields = self.fields
        for name, validators in unique_validators.items():
            for validator in validators:
                fields[name].validators.append(validator)

    def update(self, instance, validated_data):
        raise KeyError(
            "Update should never be called on a NestedSerializerBase.  Make sure parent object uses NestedSaveMixin")

    def create(self, validated_data):
        raise KeyError(
            "Update should never be called on a NestedSerializerBase.  Make sure parent object uses NestedSaveMixin")


class UpdateDoSaveMixin(NestedSaveSerializer):
    """Adds behavior to update the focal object, including M2M relations"""

    def do_update(self, match, kwargs):
        update_values = self.build_direct_values(kwargs)
        for k, v in update_values.items():
            setattr(match, k, v)
        return True

    def do_m2m_update(self, match, kwargs):
        # assign relations to forward many-to-many fields
        for field_name, field in self.fields.items():
            # we can't provide m2m values as kwargs; must use set() instead
            # we don't care whether it's forward or reverse
            # if we provide a custom serializer, it may not inherit from ManyRelatedField
            if isinstance(field, ManyRelatedField) or isinstance(self._get_model_field(field.source), ManyToManyField):
                value = kwargs.get(field_name, self._validated_data.get(field.source, empty))
                if value is empty:
                    continue  # no information
                if value is None:
                    value = []  # explicitly clear
                self.logger.debug("{}:  m2m set to {}, {}".format(self.__class__.__name__, field.source, value))
                getattr(match, field.source).set(value)


class GetOnlyNestedSerializerMixin(NestedSaveSerializer):
    """Gets (without updating) requetsed object or fails."""

    def match(self, kwargs):
        match, needs_saved = super(GetOnlyNestedSerializerMixin, self).match(kwargs)
        self.logger.debug("GetOnlyNestedSerializerMixin.match with super {} and kwargs {}".format(match, kwargs))
        if match is not None:
            return match, needs_saved
        try:
            match_on = self.build_match_on(kwargs)
            self.logger.debug("Matching on: {}".format(match_on))
            # if we don't filter().distint() we can get multiple copies of the same item and get() fails
            # we can't distinct() and select_for_update() in the same query so we must use a subquery
            return self.queryset.filter(pk__in=self.queryset.filter(**match_on).distinct()).select_for_update().get(), False
        except self.queryset.model.DoesNotExist:
            return None, False


class UpdateOnlyNestedSerializerMixin(UpdateDoSaveMixin, GetOnlyNestedSerializerMixin):
    """Gets requested object (or fails) and updates object."""


class GetOrCreateNestedSerializerMixin(GetOnlyNestedSerializerMixin):
    """Gets (without updating) or creates requested object."""

    def match(self, kwargs):
        match, needs_saved = super(GetOrCreateNestedSerializerMixin, self).match(kwargs)
        self.logger.debug("GetOrCreateNestedSerializerMixin.match with super {} and kwargs {}".format(match, kwargs))
        if match is not None:
            return match, needs_saved
        create_values = self.build_direct_values(kwargs)
        return self.queryset.model(**create_values), True


class UpdateOrCreateNestedSerializerMixin(UpdateDoSaveMixin, GetOrCreateNestedSerializerMixin):
    """Gets (without updating) or creates requested object."""


class CreateOnlyNestedSerializerMixin(GetOnlyNestedSerializerMixin):
    """Creates requested object or fails."""

    def match(self, kwargs):
        match, needs_saved = super(CreateOnlyNestedSerializerMixin, self).match(kwargs)
        self.logger.debug("CreateOnlyNestedSerializerMixin.match with super {} and kwargs {}".format(match, kwargs))
        if match is not None:
            raise IntegrityError("Matching {} object already exists".format(match.__class__.__name__))
        create_values = self.build_direct_values(kwargs)
        return self.queryset.model(**create_values), True

    def do_m2m_update(self, match, m2m_relations):
        # assign relations to forward many-to-many fields
        for k, v in m2m_relations.items():
            self.logger.debug("{}:  m2m add to {}, {}".format(self.__class__.__name__, k, v))
            getattr(match, k).add(v)
