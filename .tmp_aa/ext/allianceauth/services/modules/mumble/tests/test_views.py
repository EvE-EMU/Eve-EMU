from allianceauth.services.modules.mumble.models import MumbleUser
from django.test import TestCase, RequestFactory
from django import urls
from django.contrib.auth.models import User, Group, Permission
from django.core.exceptions import ObjectDoesNotExist

from allianceauth.tests.auth_utils import AuthUtils

MODULE_PATH = 'allianceauth.services.modules.mumble'
DEFAULT_AUTH_GROUP = 'Member'

def add_permissions():
    permission = Permission.objects.get(codename='access_mumble')
    members = Group.objects.get_or_create(name=DEFAULT_AUTH_GROUP)[0]
    AuthUtils.add_permissions_to_groups([permission], [members])

class MumbleViewsTestCase(TestCase):
    def setUp(self):
        self.member = AuthUtils.create_member('auth_member')
        self.member.email = 'auth_member@example.com'
        self.member.save()
        AuthUtils.add_main_character(self.member, 'auth_member', '12345', corp_id='111', corp_name='Test Corporation', corp_ticker='TESTR')
        self.member = User.objects.get(pk=self.member.pk)
        add_permissions()

    def login(self):
        self.client.force_login(self.member)

    def test_activate_update(self):
        self.login()
        expected_username = 'auth_member'
        expected_displayname = '[TESTR]auth_member'
        response = self.client.get(urls.reverse('mumble:activate'), follow=False)
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, expected_username)
        # create
        mumble_user = MumbleUser.objects.get(user=self.member)
        self.assertEqual(mumble_user.username, expected_username)
        self.assertEqual(str(mumble_user), expected_username)
        self.assertEqual(mumble_user.display_name, expected_displayname)
        self.assertTrue(mumble_user.pwhash)
        self.assertIn('Guest', mumble_user.groups)
        self.assertIn('Member', mumble_user.groups)
        # test update
        self.member.profile.main_character.character_name = "auth_member_updated"
        self.member.profile.main_character.corporation_ticker = "TESTU"
        self.member.profile.main_character.save()
        mumble_user = MumbleUser.objects.get(user=self.member)
        expected_displayname = '[TESTU]auth_member_updated'
        self.assertEqual(mumble_user.username, expected_username)
        self.assertEqual(str(mumble_user), expected_username)
        self.assertEqual(mumble_user.display_name, expected_displayname)
        self.assertTrue(mumble_user.pwhash)
        self.assertIn('Guest', mumble_user.groups)
        self.assertIn('Member', mumble_user.groups)


    def test_deactivate_post(self):
        self.login()
        MumbleUser.objects.create(user=self.member)

        response = self.client.post(urls.reverse('mumble:deactivate'))

        self.assertRedirects(response, expected_url=urls.reverse('services:services'), target_status_code=200)
        with self.assertRaises(ObjectDoesNotExist):
            mumble_user = User.objects.get(pk=self.member.pk).mumble

    def test_set_password(self):
        self.login()
        created = MumbleUser.objects.create(user=self.member)
        old_pwd = created.credentials.get('password')

        response = self.client.post(urls.reverse('mumble:set_password'), data={'password': '1234asdf'})

        self.assertNotEqual(MumbleUser.objects.get(user=self.member).pwhash, old_pwd)
        self.assertRedirects(response, expected_url=urls.reverse('services:services'), target_status_code=200)

    def test_reset_password(self):
        self.login()
        created = MumbleUser.objects.create(user=self.member)
        old_pwd = created.credentials.get('password')

        response = self.client.get(urls.reverse('mumble:reset_password'))

        self.assertNotEqual(MumbleUser.objects.get(user=self.member).pwhash, old_pwd)
        self.assertTemplateUsed(response, 'services/service_credentials.html')
        self.assertContains(response, 'auth_member')
