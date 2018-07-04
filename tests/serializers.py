from rest_framework import serializers
from drf_writable_nested import WritableNestedModelSerializer

from . import models


class AvatarSerializer(serializers.ModelSerializer):
    image = serializers.CharField()

    class Meta:
        model = models.Avatar
        fields = ('pk', 'image',)


class MessageSerializer(serializers.ModelSerializer):

    class Meta:
        model = models.Message
        fields = ('pk', 'message',)


class SiteSerializer(serializers.ModelSerializer):
    url = serializers.CharField()

    class Meta:
        model = models.Site
        fields = ('pk', 'url',)


class AccessKeySerializer(serializers.ModelSerializer):

    class Meta:
        model = models.AccessKey
        fields = ('pk', 'key',)


class ProfileSerializer(WritableNestedModelSerializer):
    # Direct ManyToMany relation
    sites = SiteSerializer(many=True)

    # Reverse FK relation
    avatars = AvatarSerializer(many=True)

    # Direct FK relation
    access_key = AccessKeySerializer(allow_null=True)

    # Reverse FK relation with UUID
    message_set = MessageSerializer(many=True)

    class Meta:
        model = models.Profile
        fields = ('pk', 'sites', 'avatars', 'access_key', 'message_set',)


class UserSerializer(WritableNestedModelSerializer):
    # Reverse OneToOne relation
    profile = ProfileSerializer(required=False, allow_null=True)

    class Meta:
        model = models.User
        fields = ('pk', 'profile', 'username',)


class CustomSerializer(UserSerializer):
    # Simulate having non-modelfield information on the serializer
    custom_field = serializers.CharField()

    class Meta(UserSerializer.Meta):
        fields = UserSerializer.Meta.fields + (
            'custom_field',
        )

    def validate(self, attrs):
        attrs.pop('custom_field', None)
        return attrs


class TagSerializer(serializers.ModelSerializer):

    class Meta:
        model = models.Tag
        fields = (
            'pk',
            'tag',
        )


class TaggedItemSerializer(WritableNestedModelSerializer):
    tags = TagSerializer(many=True)

    class Meta:
        model = models.TaggedItem
        fields = (
            'tags',
        )


class TeamSerializer(WritableNestedModelSerializer):
    members = UserSerializer(many=True, required=False)

    class Meta:
        model = models.Team
        fields = (
            'members',
            'name',
        )


class CustomPKSerializer(serializers.ModelSerializer):
    class Meta:
        model = models.CustomPK
        fields = (
            'slug',
        )


class UserWithCustomPKSerializer(WritableNestedModelSerializer):
    custompks = CustomPKSerializer(
        many=True,
    )

    class Meta:
        model = models.User
        fields = (
            'custompks',
            'username',
        )


class AnotherAvatarSerializer(serializers.ModelSerializer):
    image = serializers.CharField()

    class Meta:
        model = models.AnotherAvatar
        fields = ('pk', 'image',)


class AnotherProfileSerializer(WritableNestedModelSerializer):
    # Direct ManyToMany relation
    another_sites = SiteSerializer(source='sites', many=True)

    # Reverse FK relation
    another_avatars = AnotherAvatarSerializer(source='avatars', many=True)

    # Direct FK relation
    another_access_key = AccessKeySerializer(
        source='access_key', allow_null=True)

    class Meta:
        model = models.AnotherProfile
        fields = ('pk', 'another_sites', 'another_avatars',
                  'another_access_key',)


class AnotherUserSerializer(WritableNestedModelSerializer):
    # Reverse OneToOne relation
    another_profile = AnotherProfileSerializer(
        source='anotherprofile', required=False, allow_null=True)

    class Meta:
        model = models.User
        fields = ('pk', 'another_profile', 'username',)


class PageSerializer(serializers.ModelSerializer):
    class Meta:
        model = models.Page
        fields = ('pk', 'title')


class DocumentSerializer(WritableNestedModelSerializer):
    page = PageSerializer()

    class Meta:
        model = models.Document
        fields = ('pk', 'page', 'source')