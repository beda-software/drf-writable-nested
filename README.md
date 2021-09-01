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

- Python (3.5, 3.6, 3.7, 3.8, 3.9)
- Django (2.2, 3.0, 3.1, 3.2)
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

##### Update problem for nested fields with form-data in `PATCH` and `PUT` methods
There is a special problem while we try to update any model object with nested fields
within it via `PUT` or `PATCH` using form-data we can not update it. And it complains
about fields not provided. So far, we came to know that this is also a problem in DRF.
But we can follow a tricky way to solve it at least for now.
See the below solution about the problem

If you want more details, you can read related issues and articles:
https://github.com/beda-software/drf-writable-nested/issues/106
https://github.com/encode/django-rest-framework/issues/7262#issuecomment-737364846

###### Example:
```python

# Models
class Voucher(models.Model):
    voucher_number = models.CharField(verbose_name="voucher number", max_length=10, default='')
    image = models.ImageField(upload_to="vouchers/images/", null=True, blank=True)

class VoucherRow(models.Model):
    voucher = models.ForeignKey(to='voucher.Voucher', on_delete=models.PROTECT, verbose_name='voucher',
                                related_name='voucherrows', null=True)
    account = models.CharField(verbose_name="fortnox account number", max_length=255)
    debit = models.DecimalField(verbose_name="amount", decimal_places=2, default=0.00, max_digits=12)
    credit = models.DecimalField(verbose_name="amount", decimal_places=2, default=0.00, max_digits=12)
    description = models.CharField(verbose_name="description", max_length=100, null=True, blank=True)

# Serializers for these models
class VoucherRowSerializer(WritableNestedModelSerializer):
    class Meta:
        model = VoucherRow
        fields = ('id', 'account', 'debit', 'credit', 'description',)


class VoucherSerializer(serializers.ModelSerializer):
    voucherrows = VoucherRowSerializer(many=True, required=False, read_only=True)
    class Meta:
        model = Voucher
        fields = ('id', 'participants', 'voucher_number', 'voucherrows', 'image')

```

Now if you want to update `Voucher` with `VoucherRow` and voucher image then you need to do it
using form-data via `PUT` or `PATCH` request where your `voucherrows` fields are nested field.
With the current implementation of the `drf-writable-nested` doesn't update it. Because it does
not support something like-

```text
voucherrows[1].account=1120
voucherrows[1].debit=1000.00
voucherrows[1].credit=0.00
voucherrows[1].description='Debited from Bank Account' 
voucherrows[2].account=1130
voucherrows[1].debit=0.00
voucherrows[1].credit=1000.00
voucherrows[1].description='Credited to Cash Account'

```
This is not supported at least for now. So, we can achieve the result in a different way.
Instead of sending the array fields separately in this way we can convert the whole fields
along with values in a `json` string like below and set it as value to the field `voucherrows`.

```json
"[{\"account\": 1120, \"debit\": 1000.00, \"credit\": 0.00, \"description\": \"Debited from Bank Account\"}, {\"account\": 1130, \"debit\": 0.00, \"credit\": 1000.00, \"description\": \"Credited to Cash Account\"}]"
```

Now it'll be actually sent as a single field value to the application for the field `voucherrows`.
From your `views` you need to parse it like below before sending it to the serializer-

```python
class VoucherViewSet(viewsets.ModelViewSet):
    serializer_class = VoucherSerializer
    queryset = serializer_class.Meta.model.objects.all().order_by('-created_at')
    
    def update(self, request, *args, **kwargs):
        request.data.update({'voucherrows': json.loads(request.data.pop('voucherrows', None))})
        return super().update(request, *args, **kwargs)
```
Now, you'll get the `voucherrows` field with data in the right format in your serializers.
Similar approach will be also applicable for generic views for django rest framework

Authors
=======
2014-2021, beda.software
