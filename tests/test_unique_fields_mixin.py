from django.test import TestCase
from rest_framework.exceptions import ValidationError

from . import (
    models,
    serializers,
)


class UniqueFieldsMixinTestCase(TestCase):
    def test_create_update_success(self):
        serializer = serializers.UFMParentSerializer(
            data={'child': {'field': 'value'}})
        self.assertTrue(serializer.is_valid())
        parent = serializer.save()

        serializer = serializers.UFMParentSerializer(
            instance=parent,
            data={
                'pk': parent.pk,
                'child': {
                    'pk': parent.child.pk,
                    'field': 'value',
                }
            }
        )
        self.assertTrue(serializer.is_valid())
        serializer.save()

    def test_create_update_failed(self):
        # In this case everything is valid on the validation stage, because
        # UniqueValidator is skipped
        # But `save` should raise an exception on create/update

        child = models.UFMChild.objects.create(field='value')
        parent = models.UFMParent.objects.create(child=child)

        serializer = serializers.UFMParentSerializer(
            data={
                'child': {
                    'field': child.field,
                }
            }
        )

        self.assertTrue(serializer.is_valid())
        with self.assertRaises(ValidationError) as ctx:
            serializer.save()
        self.assertEqual(
            ctx.exception.detail,
            {'child': {'field': ['This field must be unique.']}}
        )

        serializer = serializers.UFMParentSerializer(
            instance=parent,
            data={
                'pk': parent.pk,
                'child': {
                    'field': child.field,
                }
            }
        )

        self.assertTrue(serializer.is_valid())
        with self.assertRaises(ValidationError) as ctx:
            serializer.save()
        self.assertEqual(
            ctx.exception.detail,
            {'child': {'field': ['This field must be unique.']}}
        )

    def test_unique_field_not_required_for_partial_updates(self):
        child = models.UFMChild.objects.create(field='value')
        serializer = serializers.UFMChildSerializer(
            instance=child,
            data={},
            partial=True
        )
        self.assertTrue(serializer.is_valid())
