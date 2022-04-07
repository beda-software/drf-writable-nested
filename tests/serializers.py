from typing import Sequence
from rest_framework import serializers
from rest_framework.exceptions import ValidationError
from rest_framework.validators import UniqueValidator

from drf_writable_nested.serializers import WritableNestedModelSerializer
from drf_writable_nested.mixins import UniqueFieldsMixin, RelatedSaveMixin, UpdateOrCreateNestedSerializerMixin

from . import models

UNIQUE_ERROR_MESSAGE = 'The value is existed'


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
        # Explicit type so that mypy doesn't complain later about a longer Tuple
        fields = ('pk', 'profile', 'username', 'user_avatar') # type: Sequence[str]


class CustomSerializer(UserSerializer):
    # Simulate having non-modelfield information on the serializer
    custom_field = serializers.CharField()

    class Meta(UserSerializer.Meta):
        fields = tuple(UserSerializer.Meta.fields) + (
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


class UFMChildSerializerForValidatorMessage(UniqueFieldsMixin,
                                            serializers.ModelSerializer):
    field = serializers.CharField(validators=[
        UniqueValidator(queryset=models.UFMChild.objects.all(),
                        message=UNIQUE_ERROR_MESSAGE
                        )
    ])

    class Meta:
        model = models.UFMChild
        fields = ('pk', 'field')


class UFMParentSerializer(WritableNestedModelSerializer):
    child = UFMChildSerializer()

    class Meta:
        model = models.UFMParent
        fields = ('pk', 'child')


class UFMParentSerializerForValidatorMessage(WritableNestedModelSerializer):
    child = UFMChildSerializerForValidatorMessage()

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


############
# NEW STYLE
############


class NewAvatarSerializer(UpdateOrCreateNestedSerializerMixin, serializers.ModelSerializer):
    image = serializers.CharField()

    class Meta:
        model = models.Avatar
        fields = ('pk', 'image',
                  # new-style serializers must include parent FK field
                  'profile',
                  )


class NewMessageSerializer(UpdateOrCreateNestedSerializerMixin, serializers.ModelSerializer):

    class Meta:
        model = models.Message
        fields = ('pk', 'message',
                  # new-style serializers must include parent FK field
                  'profile'
                  )


class NewSiteSerializer(UpdateOrCreateNestedSerializerMixin, serializers.ModelSerializer):
    url = serializers.CharField()

    class Meta:
        model = models.Site
        fields = ('pk', 'url',)


class NewAccessKeySerializer(UpdateOrCreateNestedSerializerMixin, serializers.ModelSerializer):

    class Meta:
        model = models.AccessKey
        fields = ('pk', 'key',)


class NewProfileSerializer(UpdateOrCreateNestedSerializerMixin, serializers.ModelSerializer):
    # new-style serializers can prioritize one-to-one relations by explicitly listing the one-to-one relation as the match criteria
    DEFAULT_MATCH_ON = ['user']

    # Direct ManyToMany relation
    sites = NewSiteSerializer(many=True)

    # Reverse FK relation
    avatars = NewAvatarSerializer(many=True)

    # Direct FK relation
    access_key = NewAccessKeySerializer(allow_null=True)

    # Reverse FK relation with UUID
    message_set = NewMessageSerializer(many=True)

    class Meta:
        model = models.Profile
        fields = ('pk', 'sites', 'avatars', 'access_key', 'message_set',
                  # new-style serializers must include parent FK field
                  'user',
                  )


class NewBaseProfileSerializer(UpdateOrCreateNestedSerializerMixin, serializers.ModelSerializer):
    # this top-level serializer expects to find the Profile by pk
    DEFAULT_MATCH_ON = ['pk']  # actually the default

    # Direct ManyToMany relation
    sites = NewSiteSerializer(many=True)

    # Reverse FK relation
    avatars = NewAvatarSerializer(many=True)

    # Direct FK relation
    access_key = NewAccessKeySerializer(allow_null=True)

    # Reverse FK relation with UUID
    message_set = NewMessageSerializer(many=True)

    class Meta:
        model = models.Profile
        # because this is not a nested serializer (i.e. found by parent), we don't include `user`
        fields = ('pk', 'sites', 'avatars', 'access_key', 'message_set',)


class NewUserSerializer(UpdateOrCreateNestedSerializerMixin, serializers.ModelSerializer):
    # Reverse OneToOne relation
    profile = NewProfileSerializer(required=False, allow_null=True)
    user_avatar = NewAvatarSerializer(required=False, allow_null=True)

    class Meta:
        model = models.User
        fields = ('pk', 'profile', 'username', 'user_avatar')


class NewCustomSerializer(UserSerializer):
    # Simulate having non-modelfield information on the serializer
    custom_field = serializers.CharField()

    class Meta(UserSerializer.Meta):
        fields = NewUserSerializer.Meta.fields + (
            'custom_field',
        )

    def validate(self, attrs):
        attrs.pop('custom_field', None)
        return attrs


class NewTagSerializer(UpdateOrCreateNestedSerializerMixin, serializers.ModelSerializer):

    class Meta:
        model = models.Tag
        fields = (
            'pk',
            'tag',
        )


class NewTaggedItemSerializer(RelatedSaveMixin, serializers.ModelSerializer):
    tags = NewTagSerializer(many=True)

    class Meta:
        model = models.TaggedItem
        fields = (
            'tags',
        )


class NewTeamSerializer(RelatedSaveMixin, serializers.ModelSerializer):
    members = NewUserSerializer(many=True, required=False)

    class Meta:
        model = models.Team
        fields = (
            'members',
            'name',
        )


class NewCustomPKSerializer(UpdateOrCreateNestedSerializerMixin, serializers.ModelSerializer):
    DEFAULT_MATCH_ON = ['slug']

    class Meta:
        model = models.CustomPK
        fields = (
            'slug',
            # new-style serializers must include parent FK field
            'user',
        )


class NewUserWithCustomPKSerializer(RelatedSaveMixin, serializers.ModelSerializer):
    custompks = NewCustomPKSerializer(
        many=True,
    )

    class Meta:
        model = models.User
        fields = (
            'custompks',
            'username',
        )


class NewAnotherAvatarSerializer(UpdateOrCreateNestedSerializerMixin, serializers.ModelSerializer):
    image = serializers.CharField()

    class Meta:
        model = models.AnotherAvatar
        fields = ('pk', 'image',
                  # new-style serializers must include parent FK field
                  'profile',)


# test_update_another_user_with_explicit_source expect to match an existing AnotherProfile by PK (but we get to the same place by-user)
class NewAnotherProfileSerializer(UpdateOrCreateNestedSerializerMixin, serializers.ModelSerializer):
    # new-style serializers can prioritize one-to-one relations by explicitly listing the one-to-one relation as the match criteria
    DEFAULT_MATCH_ON = ['user']

    # Direct ManyToMany relation
    another_sites = NewSiteSerializer(source='sites', many=True)

    # Reverse FK relation
    another_avatars = NewAnotherAvatarSerializer(source='avatars', many=True)

    # Direct FK relation
    another_access_key = NewAccessKeySerializer(
        source='access_key', allow_null=True)

    class Meta:
        model = models.AnotherProfile
        fields = ('pk', 'another_sites', 'another_avatars',
                  'another_access_key',
                  # new-style serializers must include parent FK field
                  'user',
                  )


# UpdateOrCreate because test_update_another_user_with_explicit_source expects serializer to find existing User by PK
class NewAnotherUserSerializer(UpdateOrCreateNestedSerializerMixin, serializers.ModelSerializer):
    # Reverse OneToOne relation
    another_profile = NewAnotherProfileSerializer(
        source='anotherprofile', required=False, allow_null=True)

    class Meta:
        model = models.User
        fields = ('pk', 'another_profile', 'username',)


class NewPageSerializer(UpdateOrCreateNestedSerializerMixin, serializers.ModelSerializer):
    class Meta:
        model = models.Page
        fields = ('pk', 'title')


class NewDocumentSerializer(RelatedSaveMixin, serializers.ModelSerializer):
    page = NewPageSerializer()

    class Meta:
        model = models.Document
        fields = ('pk', 'page', 'source')


class NewUFMChildSerializer(UniqueFieldsMixin, serializers.ModelSerializer):
    class Meta:
        model = models.UFMChild
        fields = ('pk', 'field')


class NewUFMParentSerializer(RelatedSaveMixin, serializers.ModelSerializer):
    child = NewUFMChildSerializer()

    class Meta:
        model = models.UFMParent
        fields = ('pk', 'child')


# Different relations


class NewRaiseErrorMixin(RaiseErrorMixin, UpdateOrCreateNestedSerializerMixin, serializers.ModelSerializer):
    raise_error = serializers.BooleanField(required=False, default=False)

    def save(self, **kwargs):
        raise_error = self.validated_data.pop('raise_error', False)
        if raise_error:
            raise ValidationError({'raise_error': ['should be False']})

        return super(RaiseErrorMixin, self).save(**kwargs)


class NewDirectForeignKeyChildSerializer(RaiseErrorMixin,
                                      serializers.ModelSerializer):
    class Meta:
        model = models.ForeignKeyChild
        fields = ('id', 'raise_error',)


class NewDirectForeignKeyParentSerializer(RelatedSaveMixin, serializers.ModelSerializer):
    child = NewDirectForeignKeyChildSerializer()

    class Meta:
        model = models.ForeignKeyParent
        fields = ('id', 'child',)


class NewReverseForeignKeyParentSerializer(RaiseErrorMixin,
                                        serializers.ModelSerializer):
    class Meta:
        model = models.ForeignKeyParent
        fields = ('id', 'raise_error',
                  # new-style serializers must include parent FK field
                  'child'
                  )


class NewReverseForeignKeyChildSerializer(RelatedSaveMixin, serializers.ModelSerializer):
    parents = NewReverseForeignKeyParentSerializer(many=True)

    class Meta:
        model = models.ForeignKeyChild
        fields = ('id', 'parents',)


class NewDirectOneToOneChildSerializer(RaiseErrorMixin,
                                    serializers.ModelSerializer):
    class Meta:
        model = models.OneToOneChild
        fields = ('id', 'raise_error',)


class NewDirectOneToOneParentSerializer(RelatedSaveMixin, serializers.ModelSerializer):
    child = NewDirectOneToOneChildSerializer()

    class Meta:
        model = models.OneToOneParent
        fields = ('id', 'child',)


class NewReverseOneToOneParentSerializer(RaiseErrorMixin,
                                      serializers.ModelSerializer):
    class Meta:
        model = models.OneToOneParent
        fields = ('id', 'raise_error',
                  # new-style serializers must include parent FK field
                  'child',
                  )


class NewReverseOneToOneChildSerializer(RelatedSaveMixin, serializers.ModelSerializer):
    parent = NewReverseOneToOneParentSerializer()

    class Meta:
        model = models.OneToOneChild
        fields = ('id', 'parent',)


class NewDirectManyToManyChildSerializer(RaiseErrorMixin,
                                      serializers.ModelSerializer):
    class Meta:
        model = models.ManyToManyChild
        fields = ('id', 'raise_error',)


class NewDirectManyToManyParentSerializer(RelatedSaveMixin, serializers.ModelSerializer):
    children = NewDirectManyToManyChildSerializer(many=True)

    class Meta:
        model = models.ManyToManyParent
        fields = ('id', 'children',)


class NewReverseManyToManyParentSerializer(RaiseErrorMixin,
                                        serializers.ModelSerializer):
    class Meta:
        model = models.ManyToManyParent
        fields = ('id', 'raise_error',)


class NewReverseManyToManyChildSerializer(RelatedSaveMixin, serializers.ModelSerializer):
    parents = NewReverseManyToManyParentSerializer(many=True)

    class Meta:
        model = models.ManyToManyChild
        fields = ('id', 'parents',)


class NewI86GenreNameSerializer(UpdateOrCreateNestedSerializerMixin, serializers.ModelSerializer):
    class Meta:
        model = models.I86Name
        fields = ('id', 'string',
                  # new-style serializers must include parent FK field
                  'item',
                  )


class NewI86GenreSerializer(RelatedSaveMixin, serializers.ModelSerializer):
    names = NewI86GenreNameSerializer(many=True)

    class Meta:
        model = models.I86Genre
        fields = ('id', 'names',)


class NewReadOnlyChildSerializer(UpdateOrCreateNestedSerializerMixin, serializers.ModelSerializer):
    class Meta:
        model = models.ReadOnlyChild
        fields = ('id', 'name')
        extra_kwargs = {
            'name': {'read_only': True}
        }


class NewReadOnlyParentSerializer(RelatedSaveMixin, serializers.ModelSerializer):
    child = NewReadOnlyChildSerializer(match_on=['id'])

    class Meta:
        model = models.ReadOnlyParent
        fields = ('id', 'child')
