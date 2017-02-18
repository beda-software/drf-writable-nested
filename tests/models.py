from django.db import models


class Site(models.Model):
    url = models.CharField(max_length=100)


class User(models.Model):
    username = models.CharField(max_length=100)


class Profile(models.Model):
    sites = models.ManyToManyField(Site)
    user = models.OneToOneField(User)


class Avatar(models.Model):
    image = models.CharField(max_length=100)
    profile = models.ForeignKey(Profile, related_name='avatars')

