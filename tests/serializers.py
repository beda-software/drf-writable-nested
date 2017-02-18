from rest_framework import serializers
from drf_writable_nested import WritableNestedModelSerializer

from .models import User, Profile, Site, Avatar


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


class ProfileSerializer(WritableNestedModelSerializer):
    # Direct ManyToMany relation
    sites = SiteSerializer(many=True)
    # Reverse FK relation
    avatars = AvatarSerializer(many=True)

    class Meta:
        model = Profile
        fields = ('pk', 'sites', 'avatars',)


class UserSerializer(WritableNestedModelSerializer):
    # Reverse OneToOne relation
    profile = ProfileSerializer()

    class Meta:
        model = User
        fields = ('pk', 'profile', 'username',)
