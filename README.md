DRF Writeable Nested
====================

This is a writeable nested model serializer for Django REST Framework.





Requirements
============

- Python (2.7, 3.2, 3.3, 3.4, 3.5)
- Django (1.8, 1.9, 1.10)
- djangorestframework (3.x)

Installation
============

```
pip install drf-writeable-nested
```

Usage
=====
For example, for the following model structure:
```python
from django.db import models

    
class User(models.Model):
    username = models.CharField(max_length=100) 
    
    
class Profile(models.Model):
    sites = models.ManyToManyField(Site)
    user = models.OneToOneField(User)
    
   
class Avatar(models.Model):
    image = models.CharField(max_length=100)
    profile = models.ForeignKey(Profile, related_name='profile')
    

class Site(models.Model):
    url =  models.CharField(max_length=100)
```

We should create the following list of serialzers:

```python
import serialziers from rest_framework
import WriteableNestedModelSerializer from drf_writeable_nested


class AvatarSerializer(serialziers.ModelSerializer):
    image = serialziers.CharField()
    

class SiteSerializer(serializer.ModelSerializer):
    url = serializers.CharField()


class ProfileSerializer(WriteableNestedModelSerializer):
    # Direct ManyToMany relation
    sites = SiteSerializer(many=True)
    # Reverse FK relation
    avatars = ProfileSerializer(many=True)


class UserSerializer(WriteableNestedModelSerializer):
    # Reverse OneToOne relation
    profile = ProfileSerializer()
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
Vadim Laletin at Bro.engineering
