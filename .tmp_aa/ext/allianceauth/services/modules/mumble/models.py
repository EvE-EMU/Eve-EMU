import logging
import random
import string
from typing import ClassVar

from passlib.hash import bcrypt_sha256

from django.contrib.auth.models import User
from django.db import models
from django.db.models.fields import related
from django.utils.translation import gettext_lazy as _

from allianceauth.eveonline.models import EveCharacter
from allianceauth.services.abstract import AbstractServiceModel
from allianceauth.services.hooks import NameFormatter

from .app_settings import MUMBLE_TEMPS_SSO_PREFIX
from .managers import MumbleManager

logger = logging.getLogger(__name__)


class TempLink(models.Model):
    expires = models.DateTimeField(_("Expiry"), auto_now=False, auto_now_add=False)
    link_ref = models.CharField(max_length=20)
    creator = models.ForeignKey(EveCharacter, on_delete=models.SET_NULL, null=True, default=None)

    class Meta:
        permissions = (("create_new_links", "Can Create Temp Links"),)

    def __str__(self):
        return f"Link {self.link_ref} - {self.expires}"


class MumbleUserCommon(AbstractServiceModel):
    user = models.OneToOneField(User, on_delete=models.CASCADE, primary_key=True, related_name='%(app_label)s')

    class HashFunction(models.TextChoices):
        SHA256 = 'bcrypt-sha256', _('SHA256')
        SHA1 = 'sha1', _('SHA1')
    username = models.CharField(max_length=254, unique=True)
    pwhash = models.CharField(max_length=90)
    hashfn = models.CharField(
        max_length=15,
        choices=HashFunction.choices,
        default=HashFunction.SHA256)
    certhash = models.CharField(
        verbose_name="Certificate Hash",
        max_length=254, blank=True, null=True, editable=False,
        help_text="Hash of Mumble client certificate as presented when user authenticates")
    release = models.TextField(
        verbose_name="Mumble Release",
        blank=True, null=True, editable=False,
        help_text="Client release. For official releases, this equals the version. For snapshots and git compiles, this will be something else.")
    version = models.IntegerField(
        verbose_name="Mumble Version",
        blank=True, null=True, editable=False,
        help_text="Client version. Major version in upper 16 bits, followed by 8 bits of minor version and 8 bits of patchlevel. Version 1.2.3 = 0x010203.")
    last_connect = models.DateTimeField(
        verbose_name="Last Connection",
        blank=True, null=True, editable=False,
        help_text="Timestamp of the users Last Connection to Mumble")
    last_disconnect = models.DateTimeField(
        verbose_name="Last Disconnection",
        blank=True, null=True, editable=False,
        help_text="Timestamp of the users Last Disconnection from Mumble")

    class Meta:  # pyright: ignore[reportIncompatibleVariableOverride]
        abstract = True

    def __str__(self) -> str:
        return f"{self.username}"

    def update_password(self, password=None) -> None:
        init_password = password
        logger.debug(f"Updating mumble user {self.user} password.")
        if not password:
            password = MumbleManager.generate_random_pass()
        pwhash = MumbleManager.gen_pwhash(password)
        logger.debug(f"Proceeding with mumble user {self.user} password update - pwhash starts with {pwhash[0:5]}")
        self.pwhash = pwhash
        self.hashfn = self.HashFunction.SHA256
        self.save()
        if init_password is None:
            self.credentials.update({"username": self.username, "password": password})

    def reset_password(self) -> None:
        self.update_password()


class MumbleUser(MumbleUserCommon):

    objects: ClassVar[MumbleManager] = MumbleManager()  # pyright: ignore[reportIncompatibleVariableOverride]

    @property
    def display_name(self) -> str:
        from .auth_hooks import MumbleService
        return NameFormatter(MumbleService(), self.user).format_name()

    @property
    def groups(self) -> list[str]:
        """
        Return a list of groups for a given user

        :return:
        :rtype:
        """

        groups = [self.user.profile.state.name]

        for group in self.user.groups.all():
            groups.append(str(group.name).replace(' ', '-'))

        return groups

    class Meta:  # pyright: ignore[reportIncompatibleVariableOverride]
        verbose_name = _("User")
        verbose_name_plural = _("Users")
        permissions = (
            ("access_mumble", "Can access the Mumble service"),
            ("view_connection_history", "Can access the connection history of the Mumble service"),
        )


class TempUser(MumbleUserCommon):
    user = None
    templink = models.ForeignKey(TempLink, on_delete=models.CASCADE, null=True, default=None)
    character = models.ForeignKey(EveCharacter, verbose_name=_("Character"), on_delete=models.CASCADE)

    @property
    def display_name(self) -> str:
        return f"{MUMBLE_TEMPS_SSO_PREFIX}{self.character.character_name}"

    @property
    def groups(self) -> list[str]:
        """
        Default groups for ther Temp user

        :return:
        :rtype:
        """

        return ['Guest', 'Temporary-User']

    @staticmethod
    def generate_random_pass() -> str:
        return ''.join([random.choice(string.ascii_letters + string.digits) for n in range(16)])

    @staticmethod
    def gen_pwhash(password) -> str:
        return bcrypt_sha256.encrypt(password.encode('utf-8'))

    def __str__(self) -> str:
        return f"Temp User: {self.username}"

    class Meta:  # pyright: ignore[reportIncompatibleVariableOverride]
        verbose_name = _("Temp User")
        verbose_name_plural = _("Temp Users")
        permissions = ()


class IdlerHandler(models.Model):
    name = models.CharField(_("Name"), max_length=50)
    enabled = models.BooleanField(_("Enabled"), default=False)
    seconds = models.SmallIntegerField(_("Idle Seconds"), default=3600)
    interval = models.SmallIntegerField(_("Run Interval"), default=60)
    channel = models.SmallIntegerField(_("AFK Channel"))
    denylist = models.BooleanField(_("DenyList"), default=True, help_text="True for DenyList, False for Allowlist")
    list = models.CharField(_("Allow/Deny list"), max_length=50, default="")

    class Meta:
        verbose_name = _("Idler Handler")
        verbose_name_plural = _("Idler Handlers")
        default_permissions = ()

    def __str__(self) -> str:
        return f"{self.name}"


class MumbleServerServer(models.Model):  # This will clash with ICE MumbleServer
    class ServerVersion(models.TextChoices):
        MUMBLESERVER_1_6_870 = 'MumbleServer_1_6_870.ice', _('MumbleServer.ice (Mumble-Server 1.6.870)')
        MUMBLESERVER_1_5_857 = 'MumbleServer_1_5_857.ice', _('MumbleServer.ice (Mumble-Server 1.5.857)')
        MURMUR_1_4_287 = 'Murmur_1_4_287.ice', _('Murmur.ice (Murmur 1.4.287)')
        MURMUR_1_4_274 = 'Murmur_1_4_274.ice', _('Murmur.ice (Murmur 1.4.274)')
        MURMUR_1_3_4 = 'Murmur_1_3_4.ice', _('Murmur.ice (Murmur 1.3.4)')

    name = models.CharField(max_length=50)
    ip = models.GenericIPAddressField(
        verbose_name=_("Host IP Address"),
        protocol="both",
        unpack_ipv4=False,
        default="127.0.0.1")
    endpoint = models.GenericIPAddressField(
        verbose_name=_("Endpoint IP Address"),
        protocol="both",
        unpack_ipv4=False,
        default="127.0.0.1")

    port = models.PositiveSmallIntegerField(verbose_name=_("Port"), default=6502)
    secret = models.CharField(
        verbose_name=_("ICE Secret"),
        max_length=50,
        help_text="ice_secret_read in murmur.ini, used for authenticating with the Mumble Server")
    watchdog = models.SmallIntegerField(
        verbose_name=_("Watchdog Interval"),
        default=30,
        help_text="Interval in seconds for Authenticator to check/reapply connection to Mumble Server")
    slice = models.CharField(
        max_length=32,
        choices=ServerVersion.choices,
        default=ServerVersion.MUMBLESERVER_1_6_870,
        help_text="The slice file to use for connecting to the Mumble Server. This should match the version of the Mumble Server you are running.")
    virtual_servers = models.CharField(
        verbose_name=_("Virtual Servers"),
        max_length=50,
        default="1")
    avatar_enable = models.BooleanField(
        verbose_name=_("Enable EVE Avatars"),
        default=True)
    reject_on_error = models.BooleanField(
        verbose_name=_("Reject Unauthenticated"),
        default=True)
    offset = models.IntegerField(
        verbose_name=_("ID Offset"),
        default=1000000000)
    idler_handler = models.ForeignKey(
        IdlerHandler,
        verbose_name=_("Idler Handler"),
        on_delete=models.SET_NULL,
        null=True,
        blank=True)

    class Meta:
        verbose_name = _("Mumble Server")
        verbose_name_plural = _("Mumble Servers")
        default_permissions = ()

    def __str__(self) -> str:
        return f"{self.name}"

    def virtual_servers_list(self) -> list:
        return [int(num) for num in self.virtual_servers.replace(",", " ").split() if num]
    def virtual_servers_list(self) -> list:
        return [int(num) for num in self.virtual_servers.replace(",", " ").split() if num]
