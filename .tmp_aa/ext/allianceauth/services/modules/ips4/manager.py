import logging
import random
import re
import string

from passlib.hash import bcrypt

from django.conf import settings
from django.db import connections

logger = logging.getLogger(__name__)


TABLE_PREFIX = getattr(settings, 'IPS4_TABLE_PREFIX', '')


class Ips4Manager:
    SQL_ADD_USER = rf"INSERT INTO {TABLE_PREFIX}core_members (name, email, members_pass_hash, members_pass_salt, " \
                    r"member_group_id) VALUES (%s, %s, %s, %s, %s)"
    SQL_GET_ID = rf"SELECT member_id FROM {TABLE_PREFIX}core_members WHERE name = %s"
    SQL_UPDATE_PASSWORD = rf"UPDATE {TABLE_PREFIX}core_members SET members_pass_hash = %s, members_pass_salt = %s WHERE name = %s"
    SQL_DEL_USER = rf"DELETE FROM {TABLE_PREFIX}core_members WHERE member_id = %s"

    MEMBER_GROUP_ID = 3

    @classmethod
    def add_user(cls, username, email):
        logger.debug(f"Adding new IPS4 user {username}")
        plain_password = cls.__generate_random_pass()
        hash = cls._gen_pwhash(plain_password)
        salt = cls._get_salt(hash)
        group = cls.MEMBER_GROUP_ID
        cursor = connections['ips4'].cursor()
        cursor.execute(cls.SQL_ADD_USER, [username, email, hash, salt, group])
        member_id = cls.get_user_id(username)
        return username, plain_password, member_id

    @staticmethod
    def get_user_id(username):
        cursor = connections['ips4'].cursor()
        cursor.execute(Ips4Manager.SQL_GET_ID, [username])
        row = cursor.fetchone()
        if row is not None:
            logger.debug(f"Got user id {row[0]} for username {username}")
            return row[0]
        else:
            logger.error(f"username {username} not found. Unable to determine id.")
            return None

    @staticmethod
    def __generate_random_pass():
        return ''.join([random.choice(string.ascii_letters + string.digits) for n in range(16)])

    @staticmethod
    def _gen_pwhash(password):
        return bcrypt.using(ident='2y').encrypt(password.encode('utf-8'), rounds=13)

    @staticmethod
    def _get_salt(pw_hash):
        search = re.compile(r"^\$2[a-z]?\$([0-9]+)\$(.{22})(.{31})$")
        match = re.match(search, pw_hash)
        return match.group(2)

    @staticmethod
    def delete_user(id):
        logger.debug(f"Deleting IPS4 user id {id}")
        try:
            cursor = connections['ips4'].cursor()
            cursor.execute(Ips4Manager.SQL_DEL_USER, [id])
            logger.info(f"Deleted IPS4 user {id}")
            return True
        except Exception:
            logger.exception(f"Failed to delete IPS4 user id {id}")
            return False

    @classmethod
    def update_user_password(cls, username):
        logger.debug(f"Updating IPS4 user id {id} password")
        if cls.check_user(username):
            plain_password = Ips4Manager.__generate_random_pass()
            hash = cls._gen_pwhash(plain_password)
            salt = cls._get_salt(hash)
            cursor = connections['ips4'].cursor()
            cursor.execute(cls.SQL_UPDATE_PASSWORD, [hash, salt, username])
            return plain_password
        else:
            logger.error(f"Unable to update ips4 user {username} password")
            return ""

    @staticmethod
    def check_user(username):
        logger.debug(f"Checking IPS4 username {username}")
        cursor = connections['ips4'].cursor()
        cursor.execute(Ips4Manager.SQL_GET_ID, [username])
        row = cursor.fetchone()
        if row:
            logger.debug(f"Found user {username} on IPS4")
            return True
        logger.debug(f"User {username} not found on IPS4")
        return False

    @classmethod
    def update_custom_password(cls, username, plain_password):
        logger.debug(f"Updating IPS4 user id {id} password")
        if cls.check_user(username):
            hash = cls._gen_pwhash(plain_password)
            salt = cls._get_salt(hash)
            cursor = connections['ips4'].cursor()
            cursor.execute(cls.SQL_UPDATE_PASSWORD, [hash, salt, username])
            return plain_password
        else:
            logger.error(f"Unable to update ips4 user {username} password")
            return ""
