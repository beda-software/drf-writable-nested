from django.db import models
from rest_framework import serializers, test

from drf_writable_nested import WritableNestedModelSerializer


class User(models.Model):
    username = models.CharField(max_length=100)


class Profile(models.Model):
    sites = models.ManyToManyField(Site)
    user = models.OneToOneField(User)


class Avatar(models.Model):
    image = models.CharField(max_length=100)
    profile = models.ForeignKey(Profile, related_name='profile')


class Site(models.Model):
    url = models.CharField(max_length=100)



class AvatarSerializer(serializers.ModelSerializer):
    image = serializers.CharField()


class SiteSerializer(serializers.ModelSerializer):
    url = serializers.CharField()


class ProfileSerializer(WritableNestedModelSerializer):
    # Direct ManyToMany relation
    sites = SiteSerializer(many=True)
    # Reverse FK relation
    avatars = AvatarSerializer(many=True)


class UserSerializer(WritableNestedModelSerializer):
    # Reverse OneToOne relation
    profile = ProfileSerializer()


class NestedCreatedMixinTest(test.APITestCase):
    def test_create(self):
        self.assertTrue(True)
