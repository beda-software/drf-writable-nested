from django.db import models
from django.test import TestCase
from rest_framework import serializers

from drf_writable_nested import mixins
from tests.models import LookupChild, LookupParent, LookupReverseChild, LookupOneToOneChild, LookupGrandParent, \
    M2MTarget, M2MSource


class ChildSerializer(mixins.FieldLookupMixin, serializers.ModelSerializer):
    class Meta:
        model = LookupChild
        fields = '__all__'


class ReverseChildSerializer(mixins.FieldLookupMixin, serializers.ModelSerializer):
    class Meta:
        model = LookupReverseChild
        fields = '__all__'


class OneToOneChildSerializer(mixins.FieldLookupMixin, serializers.ModelSerializer):
    class Meta:
        model = LookupOneToOneChild
        fields = '__all__'


class ParentSerializer(mixins.FieldLookupMixin, serializers.ModelSerializer):
    class Meta:
        model = LookupParent
        # otherwise child2 will get created by the ModelSerializer (and duplicate child_source)
        exclude = ['child2']
    # source of a 1:many relationship
    child = ChildSerializer()
    child_source = ChildSerializer(source='child2')
    children = ReverseChildSerializer(many=True)
    one_to_one = OneToOneChildSerializer()


class NestedParentSerializer(mixins.FieldLookupMixin, serializers.ModelSerializer):
    class Meta:
        model = LookupParent
        fields = '__all__'


class OneToOneForwardSerializer(mixins.FieldLookupMixin, serializers.ModelSerializer):
    class Meta:
        model = LookupOneToOneChild
        fields = '__all__'

    parent = NestedParentSerializer()


class GrandParentSerializer(mixins.FieldLookupMixin, serializers.ModelSerializer):
    class Meta:
        model = LookupGrandParent
        fields = '__all__'
    # source of a 1:many relationship
    child = ParentSerializer()


class M2MForwardTargetSerializer(serializers.ModelSerializer):
    class Meta:
        model = M2MTarget
        fields = '__all__'


class M2MForwardSourceSerializer(mixins.FieldLookupMixin, serializers.ModelSerializer):
    class Meta:
        model = M2MSource
        fields = '__all__'
    forward = M2MForwardTargetSerializer(many=True)


class M2MReverseTargetSerializer(serializers.ModelSerializer):
    class Meta:
        model = M2MSource
        fields = '__all__'


class M2MReverseSourceSerializer(mixins.FieldLookupMixin, serializers.ModelSerializer):
    class Meta:
        model = M2MTarget
        fields = '__all__'
    reverse = M2MReverseTargetSerializer(many=True)


class GetModelFieldTest(TestCase):
    """Field types are determined by accessing the model.  These test confirm that the methods for identifying these
    fields do not change."""

    def test_fk(self):
        """Confirm that the test works correctly for fields with a source value"""
        serializer = ParentSerializer()
        model_field = serializer._get_model_field(serializer.fields['child'].source)
        self.assertIsInstance(
            model_field,
            models.ForeignKey,
            "Found {}, expected ForeignKey".format(type(model_field))
        )

    def test_fk_source(self):
        """Confirm that the test works correctly for fields with a source value"""
        serializer = ParentSerializer()
        model_field = serializer._get_model_field(serializer.fields['child_source'].source)
        self.assertIsInstance(
            model_field,
            models.ForeignKey,
            "Found {}, expected ForeignKey".format(type(model_field))
        )

    def test_reverse_fk(self):
        """Confirm that a reverse ForeignKey is a ManyToOneRel"""
        serializer = ParentSerializer()
        model_field = serializer._get_model_field(serializer.fields['children'].source)
        # opposite side of a ForeignKeyField is a ManyToOneRel
        self.assertIsInstance(
            model_field,
            models.ManyToOneRel,
            "Found {}, expected ManyToOneRel".format(type(model_field))
        )

    def test_onetoone_reverse(self):
        """A reverse OneToOne relationship is a OneToOneRel"""
        serializer = ParentSerializer()
        model_field = serializer._get_model_field(serializer.fields['one_to_one'].source)
        # opposite side of a OneToOneField is a ManyToOne
        self.assertIsInstance(
            model_field,
            models.OneToOneRel,
            "Found {}, expected OneToOneRel".format(type(model_field))
        )

    def test_onetoone_forward(self):
        """A forward OneToOne relationship is a OneToOneField"""
        serializer = OneToOneForwardSerializer()
        model_field = serializer._get_model_field(serializer.fields['parent'].source)
        # opposite side of a OneToOneField is a ManyToOne
        self.assertIsInstance(
            model_field,
            models.OneToOneField,
            "Found {}, expected OneToOneRel".format(type(model_field))
        )

    def test_m2m_reverse(self):
        """A reverse OneToOne relationship is a OneToOneRel"""
        serializer = M2MReverseSourceSerializer()
        model_field = serializer._get_model_field(serializer.fields['reverse'].source)
        # opposite side of a OneToOneField is a ManyToOne
        self.assertIsInstance(
            model_field,
            models.ManyToManyRel,
            "Found {}, expected ManyToManyRel".format(type(model_field))
        )

    def test_m2m_forward(self):
        """A forward OneToOne relationship is a OneToOneField"""
        serializer = M2MForwardSourceSerializer()
        model_field = serializer._get_model_field(serializer.fields['forward'].source)
        # opposite side of a OneToOneField is a ManyToOne
        self.assertIsInstance(
            model_field,
            models.ManyToManyField,
            "Found {}, expected ManyToManyField".format(type(model_field))
        )


class FieldTypesTest(TestCase):
    """Tests resolution of field types.  ID is always read-only."""

    def test_field_types_grandparent(self):
        """Nested serializer should be direct"""
        serializer = GrandParentSerializer()
        self.assertEqual(
            {
                'id': serializer.TYPE_READ_ONLY,
                'child': serializer.TYPE_DIRECT,
            },
            serializer.field_types
        )

    def test_field_types_parent(self):
        """Reverse one-to-one and reverse FK should be classified as Reverse"""
        serializer = ParentSerializer()
        self.assertEqual(
            {
                'id': serializer.TYPE_READ_ONLY,
                'child': serializer.TYPE_DIRECT,
                'child_source': serializer.TYPE_DIRECT,
                'children': serializer.TYPE_REVERSE,
                'one_to_one': serializer.TYPE_REVERSE,
            },
            serializer.field_types
        )

    def test_field_sources_parent(self):
        """Reverse one-to-one and reverse FK should be classified as Reverse"""
        serializer = ParentSerializer()
        self.assertEqual(
            {
                'id': serializer.TYPE_READ_ONLY,
                'child': serializer.TYPE_DIRECT,
                'child2': serializer.TYPE_DIRECT,
                'children': serializer.TYPE_REVERSE,
                'one_to_one': serializer.TYPE_REVERSE,
            },
            serializer.field_sources
        )

    def test_field_types_child(self):
        """"""
        serializer = ChildSerializer()
        self.assertEqual(
            {
                'id': serializer.TYPE_READ_ONLY,
                'name': serializer.TYPE_LOCAL,
            },
            serializer.field_types
        )

    def test_field_types_reversechild(self):
        serializer = ReverseChildSerializer()
        self.assertEqual(
            {
                'id': serializer.TYPE_READ_ONLY,
                'name': serializer.TYPE_LOCAL,
                # must have a nested serializer to be "direct" otherwise it's just a local value
                'parent': serializer.TYPE_LOCAL,
            },
            serializer.field_types
        )

    def test_field_types_onetoone_reverse(self):
        serializer = OneToOneChildSerializer()
        self.assertEqual(
            {
                'id': serializer.TYPE_READ_ONLY,
                'name': serializer.TYPE_LOCAL,
                # must have a nested serializer to be "direct" otherwise it's just a local value
                'parent': serializer.TYPE_LOCAL,
            },
            serializer.field_types
        )

    def test_field_types_onetoone_forward(self):
        serializer = OneToOneForwardSerializer()
        self.assertEqual(
            {
                'id': serializer.TYPE_READ_ONLY,
                'name': serializer.TYPE_LOCAL,
                # must have a nested serializer to be "direct" otherwise it's just a local value
                'parent': serializer.TYPE_DIRECT,
            },
            serializer.field_types
        )
