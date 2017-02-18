DRF Writable Nested
====================

This is a writable nested model serializer for Django REST Framework.

Requirements
============

- Python (2.7, 3.2, 3.3, 3.4, 3.5)
- Django (1.8, 1.9, 1.10)
- djangorestframework (3.x)

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

We should create the following list of serialzers:

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
        
    # Optional callback - will be called after reverse relations will be saved 
    def after_reverse_relations_saved(self, instance):
        after_reverse_relations_saved_callback()
    
    # Optional callback - will be called after profile relation will be saved
    def after_profile_saved(self):
        after_profile_saved_callback()
```

Also, you can use `NestedCreateMixin` or `NestedUpdateMixin` if you want 
to implement only create or update logic.

For example, if we have `/user/` endpoint for user creation with `UserSerializer`, 
we should send the following data:

```json
{
    "username": "test",
    "profile": {
        "sites": [
            {
                "url": "http://google.com"   
            },
            {
                "url": "http://yahoo.com"   
            }
        ],
        "avatars": [
            {
                "image": "image-1.png"
            },
            {
                "image": "image-2.png"
            }  
        ]
    }
}
```

This package automatically will create all relations and we can see the output 
like the following example:
```json
{
    "pk": 1,
    "username": "test",
    "profile": {
        "pk": 1,
        "sites": [
            {
                "pk": 1,
                "url": "http://google.com"   
            },
            {
                "pk": 2,
                "url": "http://yahoo.com"   
            }
        ],
        "avatars": [
            {
                "pk": 1,
                "image": "image-1.png"
            },
            {
                "pk": 2,
                "image": "image-2.png"
            }  
        ]
    }
}
```

Authors
=======
Bro.engineering
