from django.contrib.auth import get_user_model
from django.db import IntegrityError
from django.test import TestCase, RequestFactory
from rest_framework import serializers

from drf_writable_nested import mixins
from tests.models import Child, Parent, ParentMany, ReverseParent, ReverseChild, ReverseManyParent, ReverseManyChild, \
    GrandParent, ContextChild, NewUser, NewProfile


#########################
# GetOrCreate Serializer
#########################
class ChildGetOrCreateSerializer(mixins.GetOrCreateNestedSerializerMixin, serializers.ModelSerializer):
    DEFAULT_MATCH_ON = ['name']

    class Meta:
        model = Child
        fields = '__all__'


class GenericParentRelatedSaveSerializer(mixins.RelatedSaveMixin):
    class Meta:
        fields = '__all__'
    # source of a 1:many relationship
    child = ChildGetOrCreateSerializer()

    def create(self, validated_data):
        # "container only", no create logic
        return validated_data


##################
# Direct Relation
##################
class ParentRelatedSaveSerializer(mixins.RelatedSaveMixin, serializers.ModelSerializer):
    class Meta:
        model = Parent
        fields = '__all__'
    # source of a 1:many relationship
    child = ChildGetOrCreateSerializer()


class ParentManyRelatedSaveSerializer(mixins.RelatedSaveMixin, serializers.ModelSerializer):
    class Meta:
        model = ParentMany
        fields = '__all__'
    # source of a m2m relationship
    children = ChildGetOrCreateSerializer(many=True)


###################
# Reverse Relation
###################
class ReverseChildGetOrCreateSerializer(mixins.GetOrCreateNestedSerializerMixin, serializers.ModelSerializer):
    DEFAULT_MATCH_ON = ['name']

    class Meta:
        model = ReverseChild
        fields = '__all__'


class ReverseManyChildGetOrCreateSerializer(mixins.GetOrCreateNestedSerializerMixin, serializers.ModelSerializer):
    DEFAULT_MATCH_ON = ['name']

    class Meta:
        model = ReverseManyChild
        fields = '__all__'


class ReverseParentRelatedSaveSerializer(mixins.RelatedSaveMixin, serializers.ModelSerializer):
    class Meta:
        model = ReverseParent
        fields = '__all__'
    # target of a 1:many relationship
    children = ReverseChildGetOrCreateSerializer(many=True)


class ReverseParentGetOnlySerializer(mixins.GetOnlyNestedSerializerMixin, serializers.ModelSerializer):
    class Meta:
        model = ReverseParent
        fields = '__all__'
    # target of a m2m relationship
    children = ReverseChildGetOrCreateSerializer(many=True)


class ReverseManyParentRelatedSaveSerializer(mixins.RelatedSaveMixin, serializers.ModelSerializer):
    class Meta:
        model = ReverseManyParent
        fields = '__all__'
    # target of a m2m relationship
    children = ReverseManyChildGetOrCreateSerializer(many=True)


class WritableNestedModelSerializerTest(TestCase):

    def test_generic_nested_create(self):
        data = {
            "child": {
                "name": "test",
            }
        }

        serializer = GenericParentRelatedSaveSerializer(data=data)
        valid = serializer.is_valid()
        self.assertTrue(
            valid,
            "Serializer should have been valid:  {}".format(serializer.errors)
        )
        instance = serializer.save()
        self.assertIsInstance(
            instance,
            dict,
        )
        self.assertIn(
            'child',
            instance,
        )
        self.assertIsInstance(
            instance['child'],
            Child,
        )
        self.assertEqual(
            'test',
            instance['child'].name,
        )

    def test_generic_nested_get(self):
        """A second run with a GetOrCreate nested serializer should find same child object (by name)"""
        data = {
            "child": {
                "name": "test",
            }
        }

        serializer = GenericParentRelatedSaveSerializer(data=data)
        valid = serializer.is_valid()
        self.assertTrue(
            valid,
            "Serializer should have been valid:  {}".format(serializer.errors)
        )
        serializer.save()

        serializer = GenericParentRelatedSaveSerializer(data=data)
        valid = serializer.is_valid()
        self.assertTrue(
            valid,
            "Serializer should have been valid:  {}".format(serializer.errors)
        )
        serializer.save()

        self.assertEqual(
            1,
            Child.objects.count(),
        )

    def test_direct_nested_create(self):
        data = {
            "child": {
                "name": "test",
            }
        }

        serializer = ParentRelatedSaveSerializer(data=data)
        valid = serializer.is_valid()
        self.assertTrue(
            valid,
            "Serializer should have been valid:  {}".format(serializer.errors)
        )
        serializer.save()

    def test_direct_nested_get(self):
        """A second run with a GetOrCreate nested serializer should find same child object (by name)"""
        data = {
            "child": {
                "name": "test",
            }
        }

        serializer = ParentRelatedSaveSerializer(data=data)
        valid = serializer.is_valid()
        self.assertTrue(
            valid,
            "Serializer should have been valid:  {}".format(serializer.errors)
        )
        serializer.save()

        serializer = ParentRelatedSaveSerializer(data=data)
        valid = serializer.is_valid()
        self.assertTrue(
            valid,
            "Serializer should have been valid:  {}".format(serializer.errors)
        )
        serializer.save()

        self.assertEqual(
            2,
            Parent.objects.count()
        )

        self.assertEqual(
            1,
            Child.objects.count(),
        )

    def test_direct_many_nested_create(self):
        data = {
            "children": [{
                "name": "test",
            }]
        }

        serializer = ParentManyRelatedSaveSerializer(data=data)
        valid = serializer.is_valid()
        self.assertTrue(
            valid,
            "Serializer should have been valid:  {}".format(serializer.errors)
        )
        serializer.save()

    def test_direct_many_nested_get(self):
        """A second run with a GetOrCreate nested serializer should find same child object (by name)"""
        data = {
            "children": [{
                "name": "test",
            }]
        }

        serializer = ParentManyRelatedSaveSerializer(data=data)
        valid = serializer.is_valid()
        self.assertTrue(
            valid,
            "Serializer should have been valid:  {}".format(serializer.errors)
        )
        serializer.save()

        serializer = ParentManyRelatedSaveSerializer(data=data)
        valid = serializer.is_valid()
        self.assertTrue(
            valid,
            "Serializer should have been valid:  {}".format(serializer.errors)
        )
        serializer.save()

        self.assertEqual(
            1,
            Child.objects.count(),
        )

    def test_reverse_nested_create(self):
        data = {
            "children": [{
                "name": "test",
            }]
        }

        serializer = ReverseParentRelatedSaveSerializer(data=data)
        valid = serializer.is_valid()
        self.assertTrue(
            valid,
            "Serializer should have been valid:  {}".format(serializer.errors)
        )
        serializer.save()

    def test_reverse_nested_get(self):
        """A second run with a GetOrCreate nested serializer should find same child object (by name)"""
        data = {
            "children": [{
                "name": "test",
            }]
        }

        serializer = ReverseParentRelatedSaveSerializer(data=data)
        valid = serializer.is_valid()
        self.assertTrue(
            valid,
            "Serializer should have been valid:  {}".format(serializer.errors)
        )
        serializer.save()

        serializer = ReverseParentRelatedSaveSerializer(data=data)
        valid = serializer.is_valid()
        self.assertTrue(
            valid,
            "Serializer should have been valid:  {}".format(serializer.errors)
        )
        serializer.save()

        self.assertEqual(
            2,
            ReverseParent.objects.count()
        )

        self.assertEqual(
            1,
            ReverseChild.objects.count(),
        )

    def test_reverse_many_nested_create(self):
        data = {
            "children": [{
                "name": "test",
            }]
        }

        serializer = ReverseManyParentRelatedSaveSerializer(data=data)
        valid = serializer.is_valid()
        self.assertTrue(
            valid,
            "Serializer should have been valid:  {}".format(serializer.errors)
        )
        serializer.save()

    def test_reverse_many_nested_get(self):
        """A second run with a GetOrCreate nested serializer should find same child object (by name)"""
        data = {
            "children": [{
                "name": "test",
            }]
        }

        serializer = ReverseManyParentRelatedSaveSerializer(data=data)
        valid = serializer.is_valid()
        self.assertTrue(
            valid,
            "Serializer should have been valid:  {}".format(serializer.errors)
        )
        serializer.save()

        serializer = ReverseManyParentRelatedSaveSerializer(data=data)
        valid = serializer.is_valid()
        self.assertTrue(
            valid,
            "Serializer should have been valid:  {}".format(serializer.errors)
        )
        serializer.save()

        self.assertEqual(
            1,
            ReverseManyChild.objects.count(),
        )

    def test_reverse_set(self):
        """We had to implement a workaround because `set` does not work correctly on non-nullable reverse FKs"""
        parent = ReverseParent()
        parent.save()

        child1 = ReverseChild(name='test1', parent=parent)
        child1.save()
        child2 = ReverseChild(name='test2', parent=parent)
        child2.save()
        child3 = ReverseChild(name='test3', parent=parent)
        child3.save()
        # set is supposed to remove missing children
        parent.children.set([child1, child3])

        # if this ever fails (i.e. returns 2), we may be able to rip out the manual reverse-FK update logic
        self.assertEqual(
            3,
            parent.children.count()
        )
        
    def test_reverse_match(self):
        p = ReverseParent.objects.create()
        ReverseChild.objects.create(
            parent=p,
            name='test1',
        )
        ReverseChild.objects.create(
            parent=p,
            name='test2',
        )
        p = ReverseParent.objects.create()
        ReverseChild.objects.create(
            parent=p,
            name='test3',
        )
        ReverseChild.objects.create(
            parent=p,
            name='test4',
        )

        serializer = ReverseParentGetOnlySerializer(
            match_on=['children'],
            data={
                'children': [
                    {
                        'name': 'test3'
                    },
                    {
                        'name': 'test5'
                    }
                ]
            }
        )
        self.assertTrue(
            serializer.is_valid()
        )
        obj = serializer.save()
        # match on child test3 was successful
        self.assertEqual(
            p,
            obj,
        )
        # has two children (i.e. test3, test5)
        self.assertEqual(
            2,
            obj.children.count(),
        )
        # contains correct children
        self.assertTrue(
            ReverseParent.objects.filter(id=p.id, children__name='test3').exists()
        )
        self.assertTrue(
            ReverseParent.objects.filter(id=p.id, children__name='test5').exists()
        )


###################
# 3-Layer Relation
###################
class NestedParentGetOrCreateSerializer(mixins.GetOrCreateNestedSerializerMixin, serializers.ModelSerializer):
    class Meta:
        model = Parent
        fields = '__all__'
    # source of a 1:many relationship
    child = ChildGetOrCreateSerializer()


class GrandParentRelatedSaveSerializer(mixins.RelatedSaveMixin, serializers.ModelSerializer):
    class Meta:
        model = GrandParent
        fields = '__all__'
    # source of a 1:many relationship
    child = NestedParentGetOrCreateSerializer()


class DoubleNestedModelSerializerTest(TestCase):

    def test_direct_nested_create(self):
        data = {
            "child": {
                "child": {
                    "name": "test",
                }
            }
        }

        serializer = GrandParentRelatedSaveSerializer(data=data)
        valid = serializer.is_valid()
        self.assertTrue(
            valid,
            "Serializer should have been valid:  {}".format(serializer.errors)
        )
        serializer.save()

        self.assertEqual(
            1,
            GrandParent.objects.count(),
        )

        self.assertEqual(
            1,
            Parent.objects.count(),
        )

        self.assertEqual(
            1,
            Child.objects.count(),
        )

        instance = serializer.save()
        self.assertIsInstance(
            instance,
            GrandParent,
        )
        self.assertIsInstance(
            instance.child,
            Parent,
        )
        self.assertIsInstance(
            instance.child.child,
            Child,
        )
        self.assertEqual(
            'test',
            instance.child.child.name,
        )


##############
# Create Only
##############
class ChildCreateOnlySerializer(mixins.CreateOnlyNestedSerializerMixin, serializers.ModelSerializer):
    DEFAULT_MATCH_ON = ['name']

    class Meta:
        model = Child
        fields = '__all__'


class ParentRelatedSaveSerializerCreateOnly(mixins.RelatedSaveMixin):
    class Meta:
        fields = '__all__'
    # source of a 1:many relationship
    child = ChildCreateOnlySerializer()

    def create(self, validated_data):
        # "container only", no create logic
        return validated_data


class CreateOnlyModelSerializerTest(TestCase):

    def test_create_match_error(self):
        """Create Only serializers will not match an existing object (despite match_on)"""
        data = {
            "child": {
                "name": "test",
            }
        }

        serializer = ParentRelatedSaveSerializerCreateOnly(data=data)
        valid = serializer.is_valid()
        self.assertTrue(
            valid,
            "Serializer should have been valid:  {}".format(serializer.errors)
        )
        serializer.save()

        self.assertEqual(
            1,
            Child.objects.count()
        )

        serializer = ParentRelatedSaveSerializerCreateOnly(data=data)
        valid = serializer.is_valid()
        self.assertTrue(
            valid,
            "Serializer should have been valid:  {}".format(serializer.errors)
        )
        with self.assertRaises(IntegrityError):
            serializer.save()

    def test_create_match_error(self):
        """Create Only serializers will error if a match is found"""
        data = {
            "child": {
                "name": "test",
            }
        }

        serializer = ParentRelatedSaveSerializerCreateOnly(data=data)
        valid = serializer.is_valid()
        self.assertTrue(
            valid,
            "Serializer should have been valid:  {}".format(serializer.errors)
        )
        serializer.save()

        self.assertEqual(
            1,
            Child.objects.count()
        )

        serializer = ParentRelatedSaveSerializerCreateOnly(data=data)
        valid = serializer.is_valid()
        self.assertTrue(
            valid,
            "Serializer should have been valid:  {}".format(serializer.errors)
        )
        with self.assertRaises(IntegrityError):
            serializer.save()


#####################
# Context Conduction
#####################
class ContextChildGetOrCreateSerializer(mixins.GetOrCreateNestedSerializerMixin, serializers.ModelSerializer):
    class Meta:
        model = ContextChild
        fields = '__all__'
        extra_kwargs = {
            'owner': {
                'default': serializers.CurrentUserDefault(),
            }
        }


class GenericContextParentRelatedSaveSerializer(mixins.RelatedSaveMixin):
    child = ContextChildGetOrCreateSerializer()

    def create(self, validated_data):
        # "container only", no create logic
        return validated_data


class GenericContextGrandParentRelatedSaveSerializer(mixins.RelatedSaveMixin):
    child = GenericContextParentRelatedSaveSerializer()

    def create(self, validated_data):
        # "container only", no create logic
        return validated_data


class ContextConductionTest(TestCase):

    def setUp(self):
        self.user = get_user_model().objects.create(username="test_user")

    def test_context_conduction(self):
        data = {
            "child": {
                "child": {
                    "name": "test",
                }
            }
        }

        request = RequestFactory()
        request.user = self.user

        serializer = GenericContextGrandParentRelatedSaveSerializer(data=data)
        serializer._context = {
            'request': request
        }
        valid = serializer.is_valid()
        self.assertTrue(
            valid,
            "Serializer should have been valid:  {}".format(serializer.errors)
        )
        serializer.save()


##################
# Wildcard Source
##################
class WildcardParentRelatedSaveSerializer(mixins.RelatedSaveMixin):
    class Meta:
        fields = '__all__'
    # makes the current class a pass-through
    parent = GenericParentRelatedSaveSerializer(source='*')

    def create(self, validated_data):
        # "container only", no create logic
        return validated_data


class WildcardSourceSerializerTest(TestCase):

    def test_wildcard_source(self):
        """Wildcard sources should be processed correctly"""
        data = {
            "child": {
                "name": "test",
            }
        }

        serializer = GenericParentRelatedSaveSerializer(data=data)
        valid = serializer.is_valid()
        self.assertTrue(
            valid,
            "Serializer should have been valid:  {}".format(serializer.errors)
        )
        instance = serializer.save()
        self.assertIsInstance(
            instance,
            dict,
        )
        self.assertIn(
            'child',
            instance,
        )
        self.assertIsInstance(
            instance['child'],
            Child,
        )
        self.assertEqual(
            'test',
            instance['child'].name,
        )


###########
# OneToOne
###########
class ProfileSerializer(mixins.GetOrCreateNestedSerializerMixin, serializers.ModelSerializer):
    class Meta:
        model = NewProfile
        fields = '__all__'


class UserSerializer(mixins.RelatedSaveMixin, serializers.ModelSerializer):
    class Meta:
        model = NewUser
        fields = '__all__'
    # makes the current class a pass-through
    profile = ProfileSerializer()


class OneToOneSerializerTest(TestCase):

    def test_onetoone_source(self):
        """Wildcard sources should be processed correctly"""
        data = {
            "username": "test user",
            "profile": {
                "age": 50,
            }
        }

        serializer = UserSerializer(data=data)
        valid = serializer.is_valid()
        self.assertTrue(
            valid,
            "Serializer should have been valid:  {}".format(serializer.errors)
        )
        instance = serializer.save()
        self.assertIsInstance(
            instance,
            NewUser,
        )
        self.assertEqual(
            "test user",
            instance.username,
        )
        self.assertIsInstance(
            instance.profile,
            NewProfile,
        )
        self.assertEqual(
            50,
            instance.profile.age,
        )
