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
    messages = MessageSerializer(many=True)

    class Meta:
        model = models.Profile
        fields = ('pk', 'sites', 'avatars', 'access_key', 'messages',)


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
    members = UserSerializer(many=True)

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
