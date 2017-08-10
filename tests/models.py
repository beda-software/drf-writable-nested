from django.contrib.contenttypes.fields import GenericForeignKey, GenericRelation
from django.contrib.contenttypes.models import ContentType
from django.db import models


class Site(models.Model):
    url = models.CharField(max_length=100)


class User(models.Model):
    username = models.CharField(max_length=100)
    user_avatar = models.ForeignKey('Avatar', null=True)


class AccessKey(models.Model):
    key = models.CharField(max_length=100)


class Profile(models.Model):
    sites = models.ManyToManyField(Site)
    user = models.OneToOneField(User)
    access_key = models.ForeignKey(AccessKey, null=True)


class AvatarQuerySet(models.QuerySet):
    def delete(self):
        for obj in self:
            if User.objects.filter(user_avatar=obj).exists():
                raise models.deletion.ProtectedError(
                    'You are trying to delete avatar which is used in as user'
                    'avatar',
                    protected_objects=[obj]
                )
            obj.delete()


class Avatar(models.Model):
    image = models.CharField(max_length=100)
    profile = models.ForeignKey(
        Profile,
        related_name='avatars',
    )

    objects = AvatarQuerySet.as_manager()


class Tag(models.Model):
    tag = models.SlugField()
    content_type = models.ForeignKey(
        ContentType,
        on_delete=models.CASCADE
    )
    object_id = models.PositiveIntegerField()
    content_object = GenericForeignKey()


class TaggedItem(models.Model):
    tags = GenericRelation(Tag)


class Team(models.Model):
    name = models.CharField(max_length=100)
    members = models.ManyToManyField(User)


class CustomPK(models.Model):
    slug = models.SlugField(
        primary_key=True,
    )
    user = models.ForeignKey(
        User,
        on_delete=models.CASCADE,
        related_name='custompks',
    )
