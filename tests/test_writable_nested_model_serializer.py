import uuid
from rest_framework.exceptions import ValidationError
from django.test import TestCase

from . import (
    models,
    serializers,
)


class WritableNestedModelSerializerTest(TestCase):
    def get_initial_data(self):
        return {
            'username': 'test',
            'profile': {
                'access_key': {
                    'key': 'key',
                },
                'sites': [
                    {
                        'url': 'http://google.com',
                    },
                    {
                        'url': 'http://yahoo.com',
                    },
                ],
                'avatars': [
                    {
                        'image': 'image-1.png',
                    },
                    {
                        'image': 'image-2.png',
                    },
                ],
                'message_set': [
                    {
                        'message': 'Message 1'
                    },
                    {
                        'message': 'Message 2'
                    },
                    {
                        'message': 'Message 3'
                    },
                ]
            },
        }

    def test_create(self):
        serializer = serializers.UserSerializer(data=self.get_initial_data())
        serializer.is_valid(raise_exception=True)
        user = serializer.save()

        self.assertIsNotNone(user)
        self.assertEqual(user.username, 'test')

        profile = user.profile
        self.assertIsNotNone(profile)
        self.assertIsNotNone(profile.access_key)
        self.assertEqual(profile.access_key.key, 'key')
        self.assertEqual(profile.sites.count(), 2)
        self.assertSetEqual(
            set(profile.sites.values_list('url', flat=True)),
            {'http://google.com', 'http://yahoo.com'}
        )
        self.assertEqual(profile.avatars.count(), 2)
        self.assertSetEqual(
            set(profile.avatars.values_list('image', flat=True)),
            {'image-1.png', 'image-2.png'}
        )

        # Check instances count
        self.assertEqual(models.User.objects.count(), 1)
        self.assertEqual(models.Profile.objects.count(), 1)
        self.assertEqual(models.Site.objects.count(), 2)
        self.assertEqual(models.Avatar.objects.count(), 2)
        self.assertEqual(models.AccessKey.objects.count(), 1)

    def test_create_with_not_specified_reverse_one_to_one(self):
        serializer = serializers.UserSerializer(data={'username': 'test',})
        serializer.is_valid(raise_exception=True)
        user = serializer.save()
        self.assertFalse(models.Profile.objects.filter(user=user).exists())

    def test_create_with_empty_reverse_one_to_one(self):
        serializer = serializers.UserSerializer(data={'username': 'test', 'profile': None})
        serializer.is_valid(raise_exception=True)
        user = serializer.save()
        self.assertFalse(models.Profile.objects.filter(user=user).exists())

    def test_create_with_custom_field(self):
        data = self.get_initial_data()
        data['custom_field'] = 'custom value'
        serializer = serializers.CustomSerializer(data=data)
        serializer.is_valid(raise_exception=True)
        user = serializer.save()
        self.assertIsNotNone(user)

    def test_create_with_generic_relation(self):
        first_tag = 'the_first_tag'
        next_tag = 'the_next_tag'
        data = {
            'tags': [
                {'tag': first_tag},
                {'tag': next_tag},
            ],
        }
        serializer = serializers.TaggedItemSerializer(data=data)
        serializer.is_valid(raise_exception=True)
        item = serializer.save()
        self.assertIsNotNone(item)
        self.assertEqual(2, models.Tag.objects.count())
        self.assertEqual(first_tag, item.tags.all()[0].tag)
        self.assertEqual(next_tag, item.tags.all()[1].tag)

    def test_update(self):
        serializer = serializers.UserSerializer(data=self.get_initial_data())
        serializer.is_valid(raise_exception=True)
        user = serializer.save()

        # Check instances count
        self.assertEqual(models.User.objects.count(), 1)
        self.assertEqual(models.Profile.objects.count(), 1)
        self.assertEqual(models.Site.objects.count(), 2)
        self.assertEqual(models.Avatar.objects.count(), 2)
        self.assertEqual(models.Message.objects.count(), 3)

        # Update
        user_pk = user.pk
        profile_pk = user.profile.pk

        message_to_update_str_pk = str(user.profile.message_set.first().pk)
        message_to_update_pk = user.profile.message_set.last().pk
        serializer = serializers.UserSerializer(
            instance=user,
            data={
                'pk': user_pk,
                'username': 'new',
                'profile': {
                    'pk': profile_pk,
                    'access_key': None,
                    'sites': [
                        {
                            'url': 'http://new-site.com',
                        },
                    ],
                    'avatars': [
                        {
                            'pk': user.profile.avatars.earliest('pk').pk,
                            'image': 'old-image-1.png',
                        },
                        {
                            'image': 'new-image-1.png',
                        },
                        {
                            'image': 'new-image-2.png',
                        },
                    ],
                    'message_set': [
                        {
                            'pk': message_to_update_str_pk,
                            'message': 'Old message 1'
                        },
                        {
                            'pk': message_to_update_pk,
                            'message': 'Old message 2'
                        },
                        {
                            'message': 'New message 1'
                        }
                    ],
                },
            },
        )

        serializer.is_valid(raise_exception=True)
        user = serializer.save()
        user.refresh_from_db()
        self.assertIsNotNone(user)
        self.assertEqual(user.pk, user_pk)
        self.assertEqual(user.username, 'new')

        profile = user.profile
        self.assertIsNotNone(profile)
        self.assertIsNone(profile.access_key)
        self.assertEqual(profile.pk, profile_pk)
        self.assertEqual(profile.sites.count(), 1)
        self.assertSetEqual(
            set(profile.sites.values_list('url', flat=True)),
            {'http://new-site.com'}
        )
        self.assertEqual(profile.avatars.count(), 3)
        self.assertSetEqual(
            set(profile.avatars.values_list('image', flat=True)),
            {'old-image-1.png', 'new-image-1.png', 'new-image-2.png'}
        )
        self.assertSetEqual(
            set(profile.message_set.values_list('message', flat=True)),
            {'Old message 1', 'Old message 2', 'New message 1'}
        )
        # Check that message which supposed to be updated still in profile
        # message_set (new message wasn't created instead of update)
        self.assertIn(
            message_to_update_pk,
            profile.message_set.values_list('id', flat=True)
        )
        self.assertIn(
            uuid.UUID(message_to_update_str_pk),
            profile.message_set.values_list('id', flat=True)
        )

        # Check instances count
        self.assertEqual(models.User.objects.count(), 1)
        self.assertEqual(models.Profile.objects.count(), 1)
        self.assertEqual(models.Avatar.objects.count(), 3)
        self.assertEqual(models.Message.objects.count(), 3)
        # Access key shouldn't be removed because it is FK
        self.assertEqual(models.AccessKey.objects.count(), 1)
        # Sites shouldn't be deleted either as it is M2M
        self.assertEqual(models.Site.objects.count(), 3)

    def test_update_raise_protected_error(self):
        serializer = serializers.UserSerializer(data=self.get_initial_data())
        serializer.is_valid(raise_exception=True)
        user = serializer.save()

        user.user_avatar = user.profile.avatars.first()
        user.save()

        serializer = serializers.ProfileSerializer(
            instance=user.profile,
            data={
                'access_key': None,
                'sites': [],
                'avatars': [
                    {
                        'pk': user.profile.avatars.last().id,
                        'image': 'old-image-1.png',
                    },
                    {
                        'image': 'new-image-1.png',
                    },
                ],
                'message_set': [],
            }
        )

        serializer.is_valid(raise_exception=True)
        with self.assertRaises(ValidationError):
            serializer.save()

        # Check that protected avatar haven't been deleted
        self.assertEqual(models.Avatar.objects.count(), 3)

    def test_update_with_empty_reverse_one_to_one(self):
        serializer = serializers.UserSerializer(data=self.get_initial_data())
        serializer.is_valid(raise_exception=True)
        user = serializer.save()
        self.assertIsNotNone(user.profile)

        serializer = serializers.UserSerializer(
            instance=user,
            data={
                'pk': user.pk,
                'username': 'new',
                'profile': None
            }
        )
        serializer.is_valid(raise_exception=True)
        user = serializer.save()
        self.assertFalse(models.Profile.objects.filter(user=user).exists())

    def test_partial_update(self):
        serializer = serializers.UserSerializer(data=self.get_initial_data())
        serializer.is_valid(raise_exception=True)
        user = serializer.save()

        # Check instances count
        self.assertEqual(models.User.objects.count(), 1)
        self.assertEqual(models.Profile.objects.count(), 1)
        self.assertEqual(models.Site.objects.count(), 2)
        self.assertEqual(models.Avatar.objects.count(), 2)
        self.assertEqual(models.AccessKey.objects.count(), 1)

        # Partial update
        user_pk = user.pk
        profile_pk = user.profile.pk

        serializer = serializers.UserSerializer(
            instance=user,
            partial=True,
            data={
                'pk': user_pk,
                'username': 'new',
            }
        )
        serializer.is_valid(raise_exception=True)
        user = serializer.save()
        user.refresh_from_db()
        self.assertIsNotNone(user)
        self.assertEqual(user.pk, user_pk)
        self.assertEqual(user.username, 'new')

        profile = user.profile
        self.assertIsNotNone(profile)
        self.assertIsNotNone(profile.access_key)
        self.assertEqual(profile.access_key.key, 'key')
        self.assertEqual(profile.pk, profile_pk)
        self.assertEqual(profile.sites.count(), 2)
        self.assertSetEqual(
            set(profile.sites.values_list('url', flat=True)),
            {'http://google.com', 'http://yahoo.com'}
        )
        self.assertEqual(profile.avatars.count(), 2)
        self.assertSetEqual(
            set(profile.avatars.values_list('image', flat=True)),
            {'image-1.png', 'image-2.png'}
        )

        # Check instances count
        self.assertEqual(models.User.objects.count(), 1)
        self.assertEqual(models.Profile.objects.count(), 1)
        self.assertEqual(models.Site.objects.count(), 2)
        self.assertEqual(models.Avatar.objects.count(), 2)
        self.assertEqual(models.AccessKey.objects.count(), 1)

    def test_partial_update_direct_fk(self):
        serializer = serializers.UserSerializer(data=self.get_initial_data())
        serializer.is_valid(raise_exception=True)
        user = serializer.save()

        # Check instances count
        self.assertEqual(models.User.objects.count(), 1)
        self.assertEqual(models.Profile.objects.count(), 1)
        self.assertEqual(models.Site.objects.count(), 2)
        self.assertEqual(models.Avatar.objects.count(), 2)
        self.assertEqual(models.AccessKey.objects.count(), 1)

        # Partial update
        user_pk = user.pk
        profile_pk = user.profile.pk
        access_key_pk = user.profile.access_key.pk

        serializer = serializers.UserSerializer(
            instance=user,
            partial=True,
            data={
                'pk': user_pk,
                'profile': {
                    'pk': profile_pk,
                    'access_key': {
                        'pk': access_key_pk,
                        'key': 'new',
                    }
                },
            }
        )
        serializer.is_valid(raise_exception=True)
        user = serializer.save()
        user.refresh_from_db()
        self.assertIsNotNone(user)
        self.assertEqual(user.pk, user_pk)
        self.assertEqual(user.username, 'test')

        profile = user.profile
        self.assertIsNotNone(profile)
        access_key = profile.access_key
        self.assertIsNotNone(access_key)
        self.assertEqual(access_key.key, 'new')
        self.assertEqual(access_key.pk, access_key_pk)

        # Check instances count
        self.assertEqual(models.User.objects.count(), 1)
        self.assertEqual(models.Profile.objects.count(), 1)
        self.assertEqual(models.Site.objects.count(), 2)
        self.assertEqual(models.Avatar.objects.count(), 2)
        self.assertEqual(models.AccessKey.objects.count(), 1)

    def test_nested_partial_update(self):
        serializer = serializers.UserSerializer(data=self.get_initial_data())
        serializer.is_valid(raise_exception=True)
        user = serializer.save()

        # Check instances count
        self.assertEqual(models.User.objects.count(), 1)
        self.assertEqual(models.Profile.objects.count(), 1)
        self.assertEqual(models.Site.objects.count(), 2)
        self.assertEqual(models.Avatar.objects.count(), 2)
        self.assertEqual(models.AccessKey.objects.count(), 1)

        # Partial update
        user_pk = user.pk
        profile_pk = user.profile.pk

        serializer = serializers.UserSerializer(
            instance=user,
            partial=True,
            data={
                'pk': user_pk,
                'profile': {
                    'pk': profile_pk,
                    'access_key': {
                        'key': 'new',
                    }
                },
            }
        )
        serializer.is_valid(raise_exception=True)
        user = serializer.save()
        user.refresh_from_db()
        self.assertIsNotNone(user)
        self.assertEqual(user.pk, user_pk)
        self.assertEqual(user.username, 'test')

        profile = user.profile
        self.assertIsNotNone(profile)
        self.assertIsNotNone(profile.access_key)
        self.assertEqual(profile.access_key.key, 'new')
        self.assertEqual(profile.pk, profile_pk)
        self.assertEqual(profile.sites.count(), 2)
        self.assertSetEqual(
            set(profile.sites.values_list('url', flat=True)),
            {'http://google.com', 'http://yahoo.com'}
        )
        self.assertEqual(profile.avatars.count(), 2)
        self.assertSetEqual(
            set(profile.avatars.values_list('image', flat=True)),
            {'image-1.png', 'image-2.png'}
        )

        # Check instances count
        self.assertEqual(models.User.objects.count(), 1)
        self.assertEqual(models.Profile.objects.count(), 1)
        self.assertEqual(models.Site.objects.count(), 2)
        self.assertEqual(models.Avatar.objects.count(), 2)
        # Old access key shouldn't be deleted
        self.assertEqual(models.AccessKey.objects.count(), 2)

    def test_update_with_generic_relation(self):
        item = models.TaggedItem.objects.create()
        serializer = serializers.TaggedItemSerializer(
            instance=item,
            data={
                'tags': [{
                    'tag': 'the_tag',
                }]
            }
        )
        serializer.is_valid(raise_exception=True)
        serializer.save()
        item.refresh_from_db()
        self.assertEqual(1, item.tags.count())

        serializer = serializers.TaggedItemSerializer(
            instance=item,
            data={
                'tags': [{
                    'pk': item.tags.get().pk,
                    'tag': 'the_new_tag',
                }]
            }
        )
        serializer.is_valid(raise_exception=True)
        serializer.save()
        item.refresh_from_db()
        self.assertEqual('the_new_tag', item.tags.get().tag)

        serializer = serializers.TaggedItemSerializer(
            instance=item,
            data={
                'tags': [{
                    'tag': 'the_third_tag',
                }]
            }
        )
        serializer.is_valid(raise_exception=True)
        serializer.save()
        item.refresh_from_db()
        self.assertEqual(1, item.tags.count())
        self.assertEqual('the_third_tag', item.tags.get().tag)

    def test_create_m2m_with_existing_related_objects(self):
        users = [
            models.User.objects.create(username='user one'),
            models.User.objects.create(username='user two'),
        ]
        user_data = serializers.UserSerializer(
            users,
            many=True
        ).data
        user_data.append({'username': 'user three'})
        user_data[0]['username'] = 'first user'
        data = {
            'name': 'Team Test',
            'members': user_data,
        }
        serializer = serializers.TeamSerializer(data=data)
        self.assertTrue(serializer.is_valid())
        team = serializer.save()
        self.assertEqual(3, team.members.count())
        self.assertEqual(3, models.User.objects.count())
        self.assertEqual('first user', team.members.first().username)

        #update
        data = serializers.TeamSerializer(team).data
        data['members'].append({'username': 'last user'})
        serializer = serializers.TeamSerializer(team, data=data)
        self.assertTrue(serializer.is_valid())
        team = serializer.save()
        self.assertEqual(4, team.members.count())
        self.assertEqual(4, models.User.objects.count())
        self.assertEqual('last user', team.members.last().username)

    def test_create_fk_with_existing_related_object(self):
        user = models.User.objects.create(username='user one')
        profile = models.Profile.objects.create(user=user)
        avatar = models.Avatar.objects.create(profile=profile)
        data = self.get_initial_data()
        data['profile']['avatars'][0]['pk'] = avatar.pk
        serializer = serializers.UserSerializer(data=data)
        self.assertTrue(serializer.is_valid())
        new_user = serializer.save()
        self.assertEqual(2, models.Avatar.objects.count())
        avatar.refresh_from_db()
        self.assertEqual('image-1.png', avatar.image)
        self.assertNotEqual(new_user.profile, profile)
        self.assertEqual(new_user.profile, avatar.profile)

    def test_create_with_existing_direct_fk_object(self):
        access_key = models.AccessKey.objects.create(
            key='the-key',
        )
        serializer = serializers.AccessKeySerializer(
            instance=access_key,
        )
        data = self.get_initial_data()
        data['profile']['access_key'] = serializer.data
        data['profile']['access_key']['key'] = 'new-key'
        serializer = serializers.UserSerializer(
            data=data,
        )
        self.assertTrue(serializer.is_valid())
        user = serializer.save()
        access_key.refresh_from_db()
        self.assertEqual(access_key, user.profile.access_key)
        self.assertEqual('new-key', access_key.key)

    def test_create_with_save_kwargs(self):
        data = self.get_initial_data()
        serializer = serializers.UserSerializer(data=data)
        serializer.is_valid(raise_exception=True)
        user = serializer.save(
            profile={
                'access_key': {'key': 'key2'},
                'sites': {'url': 'http://test.com'}
            },
        )
        self.assertEqual('key2', user.profile.access_key.key)
        sites = list(user.profile.sites.all())
        self.assertEqual('http://test.com', sites[0].url)
        self.assertEqual('http://test.com', sites[1].url)

    def test_custom_pk(self):
        data = {
            'username': 'username',
            'custompks': [{
                'slug': 'custom-key',
            }]
        }
        serializer = serializers.UserWithCustomPKSerializer(
            data=data,
        )
        self.assertTrue(serializer.is_valid())
        user = serializer.save()
        self.assertEqual('custom-key',
                         user.custompks.first().slug)
        data['custompks'].append({
            'slug': 'next-key',
        })
        data['custompks'][0]['slug'] = 'key2'
        serializer = serializers.UserWithCustomPKSerializer(
            data=data,
            instance=user,
        )
        self.assertTrue(serializer.is_valid())
        user = serializer.save()
        user.refresh_from_db()
        custompks = list(user.custompks.all())
        self.assertEqual(2, len(custompks))
        self.assertEqual('key2', custompks[0].slug)
        self.assertEqual('next-key', custompks[1].slug)
        self.assertEqual(2, models.CustomPK.objects.count())

    def get_another_initial_data(self):
        return {
            'username': 'test',
            'another_profile': {
                'another_access_key': {
                    'key': 'key',
                },
                'another_sites': [
                    {
                        'url': 'http://google.com',
                    },
                    {
                        'url': 'http://yahoo.com',
                    },
                ],
                'another_avatars': [
                    {
                        'image': 'image-1.png',
                    },
                    {
                        'image': 'image-2.png',
                    },
                ],
            },
        }

    def test_create_another_user_with_explicit_source(self):
        serializer = serializers.AnotherUserSerializer(
            data=self.get_another_initial_data())
        serializer.is_valid(raise_exception=True)
        user = serializer.save()
        self.assertIsNotNone(user)
        self.assertEqual(user.username, 'test')

        profile = user.anotherprofile
        self.assertIsNotNone(profile)
        self.assertIsNotNone(profile.access_key)
        self.assertEqual(profile.access_key.key, 'key')
        self.assertEqual(profile.sites.count(), 2)
        self.assertSetEqual(
            set(profile.sites.values_list('url', flat=True)),
            {'http://google.com', 'http://yahoo.com'}
        )
        self.assertEqual(profile.avatars.count(), 2)
        self.assertSetEqual(
            set(profile.avatars.values_list('image', flat=True)),
            {'image-1.png', 'image-2.png'}
        )
        # Check instances count
        self.assertEqual(models.User.objects.count(), 1)
        self.assertEqual(models.AnotherProfile.objects.count(), 1)
        self.assertEqual(models.Site.objects.count(), 2)
        self.assertEqual(models.AnotherAvatar.objects.count(), 2)
        self.assertEqual(models.AccessKey.objects.count(), 1)

    def test_update_another_user_with_explicit_source(self):
        serializer = serializers.AnotherUserSerializer(
            data=self.get_another_initial_data())
        serializer.is_valid(raise_exception=True)
        user = serializer.save()

        # Update
        user_pk = user.pk
        profile_pk = user.anotherprofile.pk

        serializer = serializers.AnotherUserSerializer(
            instance=user,
            data={
                'pk': user_pk,
                'username': 'new',
                'another_profile': {
                    'pk': profile_pk,
                    'another_access_key': None,
                    'another_sites': [
                        {
                            'url': 'http://new-site.com',
                        },
                    ],
                    'another_avatars': [
                        {
                            'pk': user.anotherprofile.avatars.earliest('pk').pk,
                            'image': 'old-image-1.png',
                        },
                        {
                            'image': 'new-image-1.png',
                        },
                        {
                            'image': 'new-image-2.png',
                        },
                    ],
                },
            },
        )

        serializer.is_valid(raise_exception=True)
        user = serializer.save()
        user.refresh_from_db()
        self.assertIsNotNone(user)
        self.assertEqual(user.pk, user_pk)
        self.assertEqual(user.username, 'new')

        profile = user.anotherprofile
        self.assertIsNotNone(profile)
        self.assertIsNone(profile.access_key)
        self.assertEqual(profile.pk, profile_pk)
        self.assertEqual(profile.sites.count(), 1)
        self.assertSetEqual(
            set(profile.sites.values_list('url', flat=True)),
            {'http://new-site.com'}
        )
        self.assertEqual(profile.avatars.count(), 3)
        self.assertSetEqual(
            set(profile.avatars.values_list('image', flat=True)),
            {'old-image-1.png', 'new-image-1.png', 'new-image-2.png'}
        )

        # Check instances count
        self.assertEqual(models.User.objects.count(), 1)
        self.assertEqual(models.AnotherProfile.objects.count(), 1)
        self.assertEqual(models.AnotherAvatar.objects.count(), 3)
        # Access key shouldn't be removed because it is FK
        self.assertEqual(models.AccessKey.objects.count(), 1)
        # Sites shouldn't be deleted either as it is M2M
        self.assertEqual(models.Site.objects.count(), 3)