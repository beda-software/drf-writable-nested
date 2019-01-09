DRF Writable Nested
====================
[![Build Status](https://travis-ci.org/beda-software/drf-writable-nested.svg?branch=master)](https://travis-ci.org/beda-software/drf-writable-nested)
[![codecov](https://codecov.io/gh/beda-software/drf-writable-nested/branch/master/graph/badge.svg)](https://codecov.io/gh/beda-software/drf-writable-nested)
[![pypi](https://img.shields.io/pypi/v/drf-writable-nested.svg)](https://pypi.python.org/pypi/drf-writable-nested)

This is a writable nested model serializer for Django REST Framework which
allows you to create/update your models with related nested data.

The following relations are supported:
- OneToOne (direct/reverse)
- ForeignKey (direct/reverse)
- ManyToMany (direct/reverse excluding m2m relations with through model)
- GenericRelation (this is always only reverse)

Requirements
============

- Python (2.7, 3.5, 3.6)
- Django (1.9, 1.10, 1.11, 2.0, 2.1)
- djangorestframework (3.5+)

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
    user = models.OneToOneField(User)
    access_key = models.ForeignKey(AccessKey, null=True)


class Avatar(models.Model):
    image = models.CharField(max_length=100)
    profile = models.ForeignKey(Profile, related_name='avatars')
```

We should create the following list of serializers:

```python
from rest_framework import serializers
from drf_writable_nested import WritableNestedModelSerializer


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
2014-2018, beda.software
