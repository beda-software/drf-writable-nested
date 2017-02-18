from rest_framework import serializers
from drf_writable_nested import WritableNestedModelSerializer

from .models import User, Profile, Site, Avatar, AccessKey


def after_reverse_relations_saved_callback(instance):
    pass


def after_profile_saved_callback(instance):
    pass


def after_access_key_saved_callback(instance):
    pass


def after_avatars_saved_callback(instance):
    pass


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

    def after_access_key_saved(self, instance):
        after_access_key_saved_callback(instance)

    def after_avatars_saved(self, instance):
        after_avatars_saved_callback(instance)


class UserSerializer(WritableNestedModelSerializer):
    # Reverse OneToOne relation
    profile = ProfileSerializer()

    class Meta:
        model = User
        fields = ('pk', 'profile', 'username',)

    def after_reverse_relations_saved(self, instance):
        after_reverse_relations_saved_callback(instance)

    def after_profile_saved(self, instance):
        after_profile_saved_callback(instance)
