DRF Writable Nested
====================
[![Build Status](https://travis-ci.com/beda-software/drf-writable-nested.svg?branch=master)](https://travis-ci.com/beda-software/drf-writable-nested)
[![codecov](https://codecov.io/gh/beda-software/drf-writable-nested/branch/master/graph/badge.svg)](https://codecov.io/gh/beda-software/drf-writable-nested)
[![pypi](https://img.shields.io/pypi/v/drf-writable-nested.svg)](https://pypi.python.org/pypi/drf-writable-nested)
[![pyversions](https://img.shields.io/pypi/pyversions/drf-writable-nested.svg)](https://pypi.python.org/pypi/drf-writable-nested)

This is a writable nested model serializer for Django REST Framework which
allows you to create/update your models with related nested data.

The following relations are supported:
- OneToOne (direct/reverse)
- ForeignKey (direct/reverse)
- ManyToMany (direct/reverse excluding m2m relations with through model)
- GenericRelation (this is always only reverse)

Requirements
============

- Python (3.5, 3.6, 3.7, 3.8)
- Django (2.2, 3.0, 3.1)
- djangorestframework (3.8+)

Installation
============

```
pip install drf-writable-nested
```

Usage
=====

For example, for the following model structure:
```python
from django.db import models


class Site(models.Model):
    url = models.CharField(max_length=100)


class User(models.Model):
    username = models.CharField(max_length=100)


class AccessKey(models.Model):
    key = models.CharField(max_length=100)


class Profile(models.Model):
    sites = models.ManyToManyField(Site)
    user = models.OneToOneField(User, on_delete=models.CASCADE)
    access_key = models.ForeignKey(AccessKey, null=True, on_delete=models.CASCADE)


class Avatar(models.Model):
    image = models.CharField(max_length=100)
    profile = models.ForeignKey(Profile, related_name='avatars', on_delete=models.CASCADE)
```

We should create the following list of serializers:

```python
from rest_framework import serializers
from drf_writable_nested.serializers import WritableNestedModelSerializer


class AvatarSerializer(serializers.ModelSerializer):
    image = serializers.CharField()

    class Meta:
        model = Avatar
        fields = ('pk', 'image',)


class SiteSerializer(serializers.ModelSerializer):
    url = serializers.CharField()

    class Meta:
        model = Site
        fields = ('pk', 'url',)


class AccessKeySerializer(serializers.ModelSerializer):

    class Meta:
        model = AccessKey
        fields = ('pk', 'key',)


class ProfileSerializer(WritableNestedModelSerializer):
    # Direct ManyToMany relation
    sites = SiteSerializer(many=True)

    # Reverse FK relation
    avatars = AvatarSerializer(many=True)

    # Direct FK relation
    access_key = AccessKeySerializer(allow_null=True)

    class Meta:
        model = Profile
        fields = ('pk', 'sites', 'avatars', 'access_key',)


class UserSerializer(WritableNestedModelSerializer):
    # Reverse OneToOne relation
    profile = ProfileSerializer()

    class Meta:
        model = User
        fields = ('pk', 'profile', 'username',)
```

Also, you can use `NestedCreateMixin` or `NestedUpdateMixin` from this package
if you want to support only create or update logic.

For example, we can pass the following data with related nested fields to our
main serializer:

```python
data = {
    'username': 'test',
    'profile': {
        'access_key': {
            'key': 'key',
        },
        'sites': [
            {
                'url': 'http://google.com',
            },
            {
                'url': 'http://yahoo.com',
            },
        ],
        'avatars': [
            {
                'image': 'image-1.png',
            },
            {
                'image': 'image-2.png',
            },
        ],
    },
}

user_serializer = UserSerializer(data=data)
user_serializer.is_valid(raise_exception=True)
user = user_serializer.save()
```

This serializer will automatically create all nested relations and we receive a
complete instance with filled data.
```python
user_serializer = UserSerializer(instance=user)
print(user_serializer.data)
```

```python
{
    'pk': 1,
    'username': 'test',
    'profile': {
        'pk': 1,
        'access_key': {
            'pk': 1,
            'key': 'key'
        },
        'sites': [
            {
                'pk': 1,
                'url': 'http://google.com',
            },
            {
                'pk': 2,
                'url': 'http://yahoo.com',
            },
        ],
        'avatars': [
            {
                'pk': 1,
                'image': 'image-1.png',
            },
            {
                'pk': 2,
                'image': 'image-2.png',
            },
        ],
    },
}
```

It is also possible to pass through values to nested serializers from the call
to the base serializer's `save` method. These `kwargs` must be of type `dict`. E g:

```python
# user_serializer created with 'data' as above
user = user_serializer.save(
    profile={
        'access_key': {'key': 'key2'},
    },
)
print(user.profile.access_key.key)
```

```python
'key2'
```

Note: The same value will be used for all nested instances like default value but with higher priority.


Testing
=======
To run unit tests, run:
```bash
# Setup the virtual environment
python3 -m venv envname
source envname/bin/activate

pip install django
pip install django-rest-framework
pip install -r requirements.txt

# Run tests
py.test
```


New-Style Serializers
================

In 2021, an enhanced set of mixins were added that permit fine-grained control of nested 
Serializer behavior using a `match_on` argument.  New-style serializers delegate control 
of the Create/Update behavior to the nested Serializer.  The parent Serializer need only
resolve nested serializers in the right order; this is handled by the `RelatedSaveMixin`.

New-style Serializers provide the following semantics:

 - Get:  retrieve a matching object (but DO NOT update)
 - Update:  retrieve and update a matching object
 - Create:  create an object using the entire payload
 - Combinations of the above e.g. GetOrCreate and UpdateOrCreate

The matching of `data` to a specific `instance` is driven by a list of fields found in
`match_on`.  This value is obtained from:

 - the `match_on` kwarg provided when the field is initialized
 - the DEFAULT_MATCH_ON class attribute

The new-style Serializers may be used as top-level Serializers to provide get-or-create
behaviors to DRF endpoints.  Examples of use can be found in 
`test_nested_serializer_mixins.py`.

Migration
---------

To convert an existing serializer to the new style serializers, the following procedure 
is recommended:

1. Convert nested serializers by replacing `serializers.ModelSerializer` with 
`UpdateOrCreateNestedSerializerMixin, serializers.ModelSerializer` which preserves 
backwards-compatible behavior.
1. Convert parent serializer by replacing `WritableNestedModelSerializer` with 
`RelatedSaveMixin, serializers.ModelSerializer`.
1. Verify that your test cases still pass.
1. Modify serializers (and test cases) to new-style behavior.  For example, add an 
explicit `match_on` or switch the mixin to an alternative behavior like 
`GetOrCreateNestedSerializerMixin`.

All test cases were duplicated for new-style serializers so you can see examples of 
converted serializers in `tests/serializers.py`.  For example `TeamSerializer` and 
`UserSerializer` become `NewTeamSerializer` and `NewUserSerializer`.   Examples of 
`DEFAULT_MATCH_ON` can be found in `tests/serializers.py`.  One example of an explicit
specified `match_on` is present, but non-default `match_on` values are not found in 
`tests` because they were not required to produce existing behaviors. 

NOTE:  While `RelatedSaveMixin` is the backwards-compatible mixin for the top-level
class, it is also possible to use other mixins to get complex matching behavior without
modifying the view.

Known problems with solutions
=============================


##### Validation problem for nested serializers with unique fields on update
We have a special mixin `UniqueFieldsMixin` which solves this problem.
The mixin moves` UniqueValidator`'s from the validation stage to the save stage.

If you want more details, you can read related issues and articles:
https://github.com/beda-software/drf-writable-nested/issues/1
http://www.django-rest-framework.org/api-guide/validators/#updating-nested-serializers

###### Example of usage:
```python
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

Note: `UniqueFieldsMixin` must be applied only on serializer
which has unique fields.

###### Mixin ordering
When you are using both mixins
(`UniqueFieldsMixin` and `NestedCreateMixin` or `NestedUpdateMixin`)
you should put `UniqueFieldsMixin` ahead.

For example:
```python
class ChildSerializer(UniqueFieldsMixin, NestedUpdateMixin,
        serializers.ModelSerializer):
```




Authors
=======
2014-2021, beda.software
