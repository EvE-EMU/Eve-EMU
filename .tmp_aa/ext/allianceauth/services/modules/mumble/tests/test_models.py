from allianceauth.authentication.admin import Permission
from allianceauth.tests.auth_utils import AuthUtils
from django.test import TestCase
from django.contrib.auth.models import User, Group

from ..models import (
    MumbleUser,
    IdlerHandler,
    MumbleServerServer
)

MODULE_PATH = 'allianceauth.services.modules.mumble'
DEFAULT_AUTH_GROUP = 'Member'


def add_permissions():
    permission = Permission.objects.get(codename='access_mumble')
    members = Group.objects.get_or_create(name=DEFAULT_AUTH_GROUP)[0]
    AuthUtils.add_permissions_to_groups([permission], [members])


class MumbleUserTests(TestCase):
    def setUp(self):
        self.member = AuthUtils.create_member('auth_member')
        self.member.email = 'auth_member@example.com'
        self.member.save()
        AuthUtils.add_main_character(self.member, 'john_mumble', '12345', corp_id='111', corp_name='Test Corporation', corp_ticker='TESTR')
        self.member = User.objects.get(pk=self.member.pk)
        add_permissions()
        self.mumble_user = MumbleUser.objects.create(user=self.member)

    def test_mumble_user_str(self):
        """
        Test that __str__ returns the username.
        """
        self.assertEqual(str(self.mumble_user), 'john_mumble')

    def test_update_password_no_arg(self):
        """
        Test update_password when no password is provided
        (it should generate a random one).
        """
        old_pwhash = self.mumble_user.pwhash
        self.mumble_user.update_password()  # No password argument
        # pwhash should have changed (random pass)
        self.assertNotEqual(old_pwhash, self.mumble_user.pwhash)
        self.assertTrue(self.mumble_user.credentials)  # Should have 'username' & 'password'

    def test_reset_password(self):
        """
        reset_password is basically an alias to update_password with no password argument.
        """
        old_pwhash = self.mumble_user.pwhash
        self.mumble_user.reset_password()
        self.assertNotEqual(old_pwhash, self.mumble_user.pwhash)
        self.assertTrue(self.mumble_user.credentials)


class IdlerHandlerTests(TestCase):
    def setUp(self):
        self.idler = IdlerHandler.objects.create(
            name="MyAFKIdler",
            enabled=True,
            seconds=7200,
            interval=120,
            channel=999,
            denylist=False,
            list="some_list"
        )

    def test_idler_handler_str(self):
        self.assertEqual(str(self.idler), "MyAFKIdler")


class MumbleServerServerTests(TestCase):
    def setUp(self):
        self.idler = IdlerHandler.objects.create(
            name="MyAFKIdler",
            enabled=True,
            seconds=3600,
            interval=60,
            channel=999,
            denylist=True,
            list=""
        )
        self.server = MumbleServerServer.objects.create(
            name="MyMumbleServer",
            ip="127.0.0.1",
            endpoint="127.0.0.1",
            port=6502,
            secret="supersecret",
            watchdog=30,
            slice="MumbleServer.ice",
            virtual_servers="1,2",
            avatar_enable=True,
            reject_on_error=True,
            offset=1000000000,
            idler_handler=self.idler
        )

    def test_mumble_server_str(self):
        """
        Test string representation of MumbleServerServer.
        """
        self.assertEqual(str(self.server), "MyMumbleServer")

    def test_virtual_servers_list(self):
        """
        The virtual_servers_list should parse '1,2' into [1, 2].
        """
        self.assertEqual(self.server.virtual_servers_list(), [1, 2])
