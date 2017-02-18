from rest_framework import serializers
from drf_writable_nested import WritableNestedModelSerializer

from .models import User, Profile, Site, Avatar


class AvatarSerializer(serializers.ModelSerializer):
    image = serializers.CharField()

    class Meta:
        model = Avatar

class SiteSerializer(serializers.ModelSerializer):
    url = serializers.CharField()

    class Meta:
        model = Site


class ProfileSerializer(WritableNestedModelSerializer):
    # Direct ManyToMany relation
    sites = SiteSerializer(many=True)
    # Reverse FK relation
    avatars = AvatarSerializer(many=True)

    class Meta:
        model = Profile


class UserSerializer(WritableNestedModelSerializer):
    # Reverse OneToOne relation
    profile = ProfileSerializer()

    class Meta:
        model = User
