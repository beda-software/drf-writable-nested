from django.test import TestCase
from rest_framework.exceptions import ValidationError

from . import serializers


class NestedValidationTestCase(TestCase):
    def test_save_direct_foreign_key_validation_error(self):
        serializer = serializers.DirectForeignKeyParentSerializer(
            data={
                'child': {
                    'raise_error': True,
                },
            })
        serializer.is_valid(raise_exception=True)
        with self.assertRaises(ValidationError) as ctx:
            serializer.save()

        self.assertEqual(
            ctx.exception.detail,
            {'child': {'raise_error': ['should be False']}})

    def test_save_reverse_foreign_key_validation_error(self):
        serializer = serializers.ReverseForeignKeyChildSerializer(
            data={
                'parents': [
                    {},
                    {
                        'raise_error': True,
                    },
                    {}
                ],
            })
        serializer.is_valid(raise_exception=True)
        with self.assertRaises(ValidationError) as ctx:
            serializer.save()

        self.assertEqual(
            ctx.exception.detail,
            {'parents': [{}, {'raise_error': ['should be False']}, {}]})

    def test_save_direct_one_to_one_validation_error(self):
        serializer = serializers.DirectOneToOneParentSerializer(
            data={
                'child': {
                    'raise_error': True,
                },
            })
        serializer.is_valid(raise_exception=True)
        with self.assertRaises(ValidationError) as ctx:
            serializer.save()

        self.assertEqual(
            ctx.exception.detail,
            {'child': {'raise_error': ['should be False']}})

    def test_save_reverse_one_to_one_validation_error(self):
        serializer = serializers.ReverseOneToOneChildSerializer(
            data={
                'parent': {
                    'raise_error': True,
                },
            })
        serializer.is_valid(raise_exception=True)
        with self.assertRaises(ValidationError) as ctx:
            serializer.save()

        self.assertEqual(
            ctx.exception.detail,
            {'parent': {'raise_error': ['should be False']}})

    def test_save_direct_many_to_many_validation_error(self):
        serializer = serializers.DirectManyToManyParentSerializer(
            data={
                'children': [
                    {},
                    {
                        'raise_error': True,
                    },
                    {}
                ],
            })
        serializer.is_valid(raise_exception=True)
        with self.assertRaises(ValidationError) as ctx:
            serializer.save()

        self.assertEqual(
            ctx.exception.detail,
            {'children': [{}, {'raise_error': ['should be False']}, {}]})

    def test_save_reverse_many_to_many_validation_error(self):
        serializer = serializers.ReverseManyToManyChildSerializer(
            data={
                'parents': [
                    {},
                    {
                        'raise_error': True,
                    },
                    {}
                ],
            })
        serializer.is_valid(raise_exception=True)
        with self.assertRaises(ValidationError) as ctx:
            serializer.save()

        self.assertEqual(
            ctx.exception.detail,
            {'parents': [{}, {'raise_error': ['should be False']}, {}]})
