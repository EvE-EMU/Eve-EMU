import random
import string
from allianceauth.eveonline.models import EveCharacter
from allianceauth.services.hooks import NameFormatter
from passlib.hash import bcrypt_sha256
from django.db import models
from allianceauth.services.abstract import AbstractServiceModel
import logging
from django.contrib.auth.models import User
from django.utils.translation import gettext_lazy as _

logger = logging.getLogger(__name__)


class MumbleManager(models.Manager):
    @staticmethod
    def get_username(user) -> str:
        return user.profile.main_character.character_name  # main character as the user.username may be incorrect

    @staticmethod
    def sanitise_username(username) -> str:
        return username.replace(" ", "_")

    @staticmethod
    def generate_random_pass() -> str:
        return ''.join([random.choice(string.ascii_letters + string.digits) for n in range(16)])

    @staticmethod
    def gen_pwhash(password) -> str:
        return bcrypt_sha256.encrypt(password.encode('utf-8'))

    def create(self, user):
        try:
            username = self.get_username(user)
            logger.debug(f"Creating mumble user with username {username}")
            username_clean = self.sanitise_username(username)
            password = self.generate_random_pass()
            pwhash = self.gen_pwhash(password)
            logger.debug("Proceeding with mumble user creation: clean username {}, pwhash starts with {}".format(
                username_clean, pwhash[0:5]))
            logger.info(f"Creating mumble user {username_clean}")

            result = super().create(user=user, username=username_clean, pwhash=pwhash)
            result.credentials.update({'username': result.username, 'password': password})
            return result
        except AttributeError:  # No Main or similar errors
            return False
        return False
