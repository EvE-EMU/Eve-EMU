from allianceauth.services.modules.mumble.auth_hooks import MumbleService
from allianceauth.services.modules.mumble.models import MumbleUser
from allianceauth.services.modules.mumble.tasks import MumbleTasks
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


class MumbleHooksTestCase(TestCase):
    def setUp(self):
        self.member = 'member_user'
        member = AuthUtils.create_member(self.member)
        AuthUtils.add_main_character(member, 'auth_member', '12345', corp_id='111', corp_name='Test Corporation', corp_ticker='TESTR')
        member = User.objects.get(pk=member.pk)
        MumbleUser.objects.create(user=member)
        self.none_user = 'none_user'
        none_user = AuthUtils.create_user(self.none_user)
        self.service = MumbleService
        add_permissions()

    def test_has_account(self):
        member = User.objects.get(username=self.member)
        none_user = User.objects.get(username=self.none_user)
        self.assertTrue(MumbleTasks.has_account(member))
        self.assertFalse(MumbleTasks.has_account(none_user))

    def test_service_enabled(self):
        service = self.service()
        member = User.objects.get(username=self.member)
        none_user = User.objects.get(username=self.none_user)

        self.assertTrue(service.service_active_for_user(member))
        self.assertFalse(service.service_active_for_user(none_user))

    def test_validate_user(self):
        service = self.service()
        # Test member is not deleted
        member = User.objects.get(username=self.member)
        service.validate_user(member)
        self.assertTrue(member.mumble)

        # Test none user is deleted
        none_user = User.objects.get(username=self.none_user)
        MumbleUser.objects.create(user=none_user)
        service.validate_user(none_user)
        with self.assertRaises(ObjectDoesNotExist):
            none_mumble = User.objects.get(username=self.none_user).mumble

    def test_delete_user(self):
        member = User.objects.get(username=self.member)

        service = self.service()
        result = service.delete_user(member)

        self.assertTrue(result)
        with self.assertRaises(ObjectDoesNotExist):
            mumble_user = User.objects.get(username=self.member).mumble

    def test_render_services_ctrl(self):
        service = self.service()
        member = User.objects.get(username=self.member)
        request = RequestFactory().get('/services/')
        request.user = member

        response = service.render_services_ctrl(request)
        self.assertTemplateUsed(service.service_ctrl_template)
        self.assertIn(urls.reverse('mumble:deactivate'), response)
        self.assertIn(urls.reverse('mumble:reset_password'), response)
        self.assertIn(urls.reverse('mumble:set_password'), response)

        # Test register becomes available
        member.mumble.delete()
        member = User.objects.get(username=self.member)
        request.user = member
        response = service.render_services_ctrl(request)
        self.assertIn(urls.reverse('mumble:activate'), response)
