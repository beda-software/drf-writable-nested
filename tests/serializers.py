from rest_framework import serializers
from rest_framework.exceptions import ValidationError
from drf_writable_nested import (
    WritableNestedModelSerializer, UniqueFieldsMixin)

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
    user_avatar = AvatarSerializer(required=False, allow_null=True)

    class Meta:
        model = models.User
        fields = ('pk', 'profile', 'username', 'user_avatar')


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


class CustomPKSerializer(UniqueFieldsMixin):
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


# Serializers for UniqueFieldsMixin

class UFMChildSerializer(UniqueFieldsMixin, serializers.ModelSerializer):
    class Meta:
        model = models.UFMChild
        fields = ('pk', 'field')


class UFMParentSerializer(WritableNestedModelSerializer):
    child = UFMChildSerializer()

    class Meta:
        model = models.UFMParent
        fields = ('pk', 'child')


# Different relations


class RaiseErrorMixin(serializers.ModelSerializer):
    raise_error = serializers.BooleanField(required=False, default=False)

    def save(self, **kwargs):
        raise_error = self.validated_data.pop('raise_error', False)
        if raise_error:
            raise ValidationError({'raise_error': ['should be False']})

        return super(RaiseErrorMixin, self).save(**kwargs)


class DirectForeignKeyChildSerializer(RaiseErrorMixin,
                                      serializers.ModelSerializer):
    class Meta:
        model = models.ForeignKeyChild
        fields = ('id', 'raise_error',)


class DirectForeignKeyParentSerializer(WritableNestedModelSerializer):
    child = DirectForeignKeyChildSerializer()

    class Meta:
        model = models.ForeignKeyParent
        fields = ('id', 'child',)


class ReverseForeignKeyParentSerializer(RaiseErrorMixin,
                                        serializers.ModelSerializer):
    class Meta:
        model = models.ForeignKeyParent
        fields = ('id', 'raise_error',)


class ReverseForeignKeyChildSerializer(WritableNestedModelSerializer):
    parents = ReverseForeignKeyParentSerializer(many=True)

    class Meta:
        model = models.ForeignKeyChild
        fields = ('id', 'parents',)


class DirectOneToOneChildSerializer(RaiseErrorMixin,
                                    serializers.ModelSerializer):
    class Meta:
        model = models.OneToOneChild
        fields = ('id', 'raise_error',)


class DirectOneToOneParentSerializer(WritableNestedModelSerializer):
    child = DirectOneToOneChildSerializer()

    class Meta:
        model = models.OneToOneParent
        fields = ('id', 'child',)


class ReverseOneToOneParentSerializer(RaiseErrorMixin,
                                      serializers.ModelSerializer):
    class Meta:
        model = models.OneToOneParent
        fields = ('id', 'raise_error',)


class ReverseOneToOneChildSerializer(WritableNestedModelSerializer):
    parent = ReverseOneToOneParentSerializer()

    class Meta:
        model = models.OneToOneChild
        fields = ('id', 'parent',)


class DirectManyToManyChildSerializer(RaiseErrorMixin,
                                      serializers.ModelSerializer):
    class Meta:
        model = models.ManyToManyChild
        fields = ('id', 'raise_error',)


class DirectManyToManyParentSerializer(WritableNestedModelSerializer):
    children = DirectManyToManyChildSerializer(many=True)

    class Meta:
        model = models.ManyToManyParent
        fields = ('id', 'children',)


class ReverseManyToManyParentSerializer(RaiseErrorMixin,
                                        serializers.ModelSerializer):
    class Meta:
        model = models.ManyToManyParent
        fields = ('id', 'raise_error',)


class ReverseManyToManyChildSerializer(WritableNestedModelSerializer):
    parents = ReverseManyToManyParentSerializer(many=True)

    class Meta:
        model = models.ManyToManyChild
        fields = ('id', 'parents',)


class I86GenreNameSerializer(serializers.ModelSerializer):
    class Meta:
        model = models.I86Name
        fields = ('id', 'string',)


class I86GenreSerializer(WritableNestedModelSerializer):
    names = I86GenreNameSerializer(many=True)

    class Meta:
        model = models.I86Genre
        fields = ('id', 'names',)
