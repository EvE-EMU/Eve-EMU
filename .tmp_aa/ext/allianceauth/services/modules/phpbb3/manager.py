import calendar
import logging
import random
import re
import datetime as dt
import string

from passlib.apps import phpbb3_context

from django.conf import settings
from django.db import connections

from allianceauth.eveonline.models import EveCharacter

logger = logging.getLogger(__name__)


TABLE_PREFIX = getattr(settings, 'PHPBB3_TABLE_PREFIX', 'phpbb_')


class Phpbb3Manager:
    SQL_ADD_USER =  rf"INSERT INTO {TABLE_PREFIX}users (username, username_clean, " \
                    r"user_password, user_email, group_id, user_regdate, user_permissions, " \
                    r"user_sig, user_lang) VALUES (%s, %s, %s, %s, %s, %s, %s, %s, 'en')"

    SQL_DEL_USER = rf"DELETE FROM {TABLE_PREFIX}users where username = %s"

    SQL_DIS_USER = rf"UPDATE {TABLE_PREFIX}users SET user_email= %s, user_password=%s WHERE username = %s"

    SQL_USER_ID_FROM_USERNAME = rf"SELECT user_id from {TABLE_PREFIX}users WHERE username = %s"

    SQL_ADD_USER_GROUP = rf"INSERT INTO {TABLE_PREFIX}user_group (group_id, user_id, user_pending) VALUES (%s, %s, %s)"

    SQL_GET_GROUP_ID = rf"SELECT group_id from {TABLE_PREFIX}groups WHERE group_name = %s"

    SQL_ADD_GROUP = rf"INSERT INTO {TABLE_PREFIX}groups (group_name,group_desc,group_legend) VALUES (%s,%s,0)"

    SQL_UPDATE_USER_PASSWORD = rf"UPDATE {TABLE_PREFIX}users SET user_password = %s WHERE username = %s"

    SQL_REMOVE_USER_GROUP = rf"DELETE FROM {TABLE_PREFIX}user_group WHERE user_id=%s AND group_id=%s "

    SQL_GET_ALL_GROUPS = rf"SELECT group_id, group_name FROM {TABLE_PREFIX}groups"

    SQL_GET_USER_GROUPS = rf"SELECT {TABLE_PREFIX}groups.group_name FROM {TABLE_PREFIX}groups , {TABLE_PREFIX}user_group WHERE " \
                        rf"{TABLE_PREFIX}user_group.group_id = {TABLE_PREFIX}groups.group_id AND user_id=%s"

    SQL_ADD_USER_AVATAR = rf"UPDATE {TABLE_PREFIX}users SET user_avatar_type=2, user_avatar_width=64, user_avatar_height=64, " \
                        "user_avatar=%s WHERE user_id = %s"

    SQL_CLEAR_USER_PERMISSIONS = rf"UPDATE {TABLE_PREFIX}users SET user_permissions = '' WHERE user_id = %s"

    SQL_DEL_SESSION = rf"DELETE FROM {TABLE_PREFIX}sessions where session_user_id = %s"

    SQL_DEL_AUTOLOGIN = rf"DELETE FROM {TABLE_PREFIX}sessions_keys where user_id = %s"

    def __init__(self):
        pass

    @staticmethod
    def __add_avatar(username, characterid):
        logger.debug(f"Adding EVE character id {characterid} portrait as phpbb avater for user {username}")
        avatar_url = EveCharacter.generic_portrait_url(characterid, 64)
        cursor = connections['phpbb3'].cursor()
        userid = Phpbb3Manager.__get_user_id(username)
        cursor.execute(Phpbb3Manager.SQL_ADD_USER_AVATAR, [avatar_url, userid])

    @staticmethod
    def __generate_random_pass():
        return ''.join([random.choice(string.ascii_letters + string.digits) for n in range(16)])

    @staticmethod
    def __gen_hash(password):
        return phpbb3_context.encrypt(password)

    @staticmethod
    def __santatize_username(username):
        sanatized = username.replace(" ", "_")
        sanatized = sanatized.replace("'", "_")
        return sanatized.lower()

    @staticmethod
    def _sanitize_groupname(name):
        name = name.strip(' _')
        return re.sub(r'[^\w.-]', '', name)

    @staticmethod
    def __get_group_id(groupname):
        logger.debug(f"Getting phpbb3 group id for groupname {groupname}")
        cursor = connections['phpbb3'].cursor()
        cursor.execute(Phpbb3Manager.SQL_GET_GROUP_ID, [groupname])
        row = cursor.fetchone()
        logger.debug(f"Got phpbb group id {row[0]} for groupname {groupname}")
        return row[0]

    @staticmethod
    def __get_user_id(username):
        logger.debug(f"Getting phpbb3 user id for username {username}")
        cursor = connections['phpbb3'].cursor()
        cursor.execute(Phpbb3Manager.SQL_USER_ID_FROM_USERNAME, [username])
        row = cursor.fetchone()
        if row is not None:
            logger.debug(f"Got phpbb user id {row[0]} for username {username}")
            return row[0]
        else:
            logger.error(f"Username {username} not found on phpbb. Unable to determine user id.")
            return None

    @staticmethod
    def __get_all_groups():
        logger.debug("Getting all phpbb3 groups.")
        cursor = connections['phpbb3'].cursor()
        cursor.execute(Phpbb3Manager.SQL_GET_ALL_GROUPS)
        rows = cursor.fetchall()
        out = {}
        for row in rows:
            out[row[1]] = row[0]
        logger.debug(f"Got phpbb groups {out}")
        return out

    @staticmethod
    def __get_user_groups(userid):
        logger.debug(f"Getting phpbb3 user id {userid} groups")
        cursor = connections['phpbb3'].cursor()
        cursor.execute(Phpbb3Manager.SQL_GET_USER_GROUPS, [userid])
        out = [row[0] for row in cursor.fetchall()]
        logger.debug(f"Got user {userid} phpbb groups {out}")
        return out

    @staticmethod
    def __get_current_utc_date():
        d = dt.datetime.now(dt.timezone.utc)
        unixtime = calendar.timegm(d.utctimetuple())
        return unixtime

    @staticmethod
    def __create_group(groupname):
        logger.debug(f"Creating phpbb3 group {groupname}")
        cursor = connections['phpbb3'].cursor()
        cursor.execute(Phpbb3Manager.SQL_ADD_GROUP, [groupname, groupname])
        logger.info(f"Created phpbb group {groupname}")
        return Phpbb3Manager.__get_group_id(groupname)

    @staticmethod
    def __add_user_to_group(userid, groupid):
        logger.debug(f"Adding phpbb3 user id {userid} to group id {groupid}")
        try:
            cursor = connections['phpbb3'].cursor()
            cursor.execute(Phpbb3Manager.SQL_ADD_USER_GROUP, [groupid, userid, 0])
            cursor.execute(Phpbb3Manager.SQL_CLEAR_USER_PERMISSIONS, [userid])
            logger.info(f"Added phpbb user id {userid} to group id {groupid}")
        except Exception:
            logger.exception(f"Unable to add phpbb user id {userid} to group id {groupid}")
            pass

    @staticmethod
    def __remove_user_from_group(userid, groupid):
        logger.debug(f"Removing phpbb3 user id {userid} from group id {groupid}")
        try:
            cursor = connections['phpbb3'].cursor()
            cursor.execute(Phpbb3Manager.SQL_REMOVE_USER_GROUP, [userid, groupid])
            cursor.execute(Phpbb3Manager.SQL_CLEAR_USER_PERMISSIONS, [userid])
            logger.info(f"Removed phpbb user id {userid} from group id {groupid}")
        except Exception:
            logger.exception(f"Unable to remove phpbb user id {userid} from group id {groupid}")
            pass

    @staticmethod
    def add_user(username, email, groups, characterid):
        logger.debug(f"Adding phpbb user with username {username}, email {email}, groups {groups}, characterid {characterid}")
        cursor = connections['phpbb3'].cursor()

        username_clean = Phpbb3Manager.__santatize_username(username)
        password = Phpbb3Manager.__generate_random_pass()
        pwhash = Phpbb3Manager.__gen_hash(password)
        logger.debug(f"Proceeding to add phpbb user {username_clean} and pwhash starting with {pwhash[0:5]}")
        # check if the username was simply revoked
        if Phpbb3Manager.check_user(username_clean):
            logger.warning(f"Unable to add phpbb user with username {username} - already exists. Updating user instead.")
            Phpbb3Manager.__update_user_info(username_clean, email, pwhash)
        else:
            try:

                cursor.execute(Phpbb3Manager.SQL_ADD_USER, [username_clean, username_clean, pwhash,
                                                            email, 2, Phpbb3Manager.__get_current_utc_date(),
                                                            "", ""])
                Phpbb3Manager.update_groups(username_clean, groups)
                Phpbb3Manager.__add_avatar(username_clean, characterid)
                logger.info(f"Added phpbb user {username_clean}")
            except Exception:
                logger.exception(f"Unable to add phpbb user {username_clean}")
                pass

        return username_clean, password

    @staticmethod
    def disable_user(username):
        logger.debug(f"Disabling phpbb user {username}")
        cursor = connections['phpbb3'].cursor()

        password = Phpbb3Manager.__gen_hash(Phpbb3Manager.__generate_random_pass())
        revoke_email = "revoked@localhost"
        try:
            pwhash = Phpbb3Manager.__gen_hash(password)
            cursor.execute(Phpbb3Manager.SQL_DIS_USER, [revoke_email, pwhash, username])
            userid = Phpbb3Manager.__get_user_id(username)
            cursor.execute(Phpbb3Manager.SQL_DEL_AUTOLOGIN, [userid])
            cursor.execute(Phpbb3Manager.SQL_DEL_SESSION, [userid])
            Phpbb3Manager.update_groups(username, [])
            logger.info(f"Disabled phpbb user {username}")
            return True
        except TypeError:
            logger.exception(f"TypeError occured while disabling user {username} - failed to disable.")
            return False

    @staticmethod
    def delete_user(username):
        logger.debug(f"Deleting phpbb user {username}")
        cursor = connections['phpbb3'].cursor()

        if Phpbb3Manager.check_user(username):
            cursor.execute(Phpbb3Manager.SQL_DEL_USER, [username])
            logger.info(f"Deleted phpbb user {username}")
            return True
        logger.error(f"Unable to delete phpbb user {username} - user not found on phpbb.")
        return False

    @staticmethod
    def update_groups(username, groups):
        userid = Phpbb3Manager.__get_user_id(username)
        logger.debug(f"Updating phpbb user {username} with id {userid} groups {groups}")
        if userid is not None:
            forum_groups = Phpbb3Manager.__get_all_groups()
            user_groups = set(Phpbb3Manager.__get_user_groups(userid))
            act_groups = {Phpbb3Manager._sanitize_groupname(g) for g in groups}
            addgroups = act_groups - user_groups
            remgroups = user_groups - act_groups
            logger.info(f"Updating phpbb user {username} groups - adding {addgroups}, removing {remgroups}")
            for g in addgroups:
                if g not in forum_groups:
                    forum_groups[g] = Phpbb3Manager.__create_group(g)
                Phpbb3Manager.__add_user_to_group(userid, forum_groups[g])

            for g in remgroups:
                Phpbb3Manager.__remove_user_from_group(userid, forum_groups[g])

    @staticmethod
    def remove_group(username, group):
        logger.debug(f"Removing phpbb user {username} from group {group}")
        cursor = connections['phpbb3'].cursor()
        userid = Phpbb3Manager.__get_user_id(username)
        if userid is not None:
            groupid = Phpbb3Manager.__get_group_id(group)

            if userid:
                if groupid:
                    try:
                        cursor.execute(Phpbb3Manager.SQL_REMOVE_USER_GROUP, [userid, groupid])
                        logger.info(f"Removed phpbb user {username} from group {group}")
                    except Exception:
                        logger.exception(
                            f"Exception prevented removal of phpbb user {username} with id {userid} from group {group} with id {groupid}")
                        pass

    @staticmethod
    def check_user(username):
        logger.debug(f"Checking phpbb username {username}")
        cursor = connections['phpbb3'].cursor()
        cursor.execute(Phpbb3Manager.SQL_USER_ID_FROM_USERNAME, [Phpbb3Manager.__santatize_username(username)])
        row = cursor.fetchone()
        if row:
            logger.debug(f"Found user {username} on phpbb")
            return True
        logger.debug(f"User {username} not found on phpbb")
        return False

    @staticmethod
    def update_user_password(username, characterid, password=None):
        logger.debug(f"Updating phpbb user {username} password")
        cursor = connections['phpbb3'].cursor()
        if not password:
            password = Phpbb3Manager.__generate_random_pass()
        if Phpbb3Manager.check_user(username):
            pwhash = Phpbb3Manager.__gen_hash(password)
            logger.debug(
                f"Proceeding to update phpbb user {username} password with pwhash starting with {pwhash[0:5]}")
            cursor.execute(Phpbb3Manager.SQL_UPDATE_USER_PASSWORD, [pwhash, username])
            Phpbb3Manager.__add_avatar(username, characterid)
            logger.info(f"Updated phpbb user {username} password.")
            return password
        logger.error(f"Unable to update phpbb user {username} password - user not found on phpbb.")
        return ""

    @staticmethod
    def __update_user_info(username, email, password):
        logger.debug(
            f"Updating phpbb user {username} info: username {email} password of length {len(password)}")
        cursor = connections['phpbb3'].cursor()
        try:
            cursor.execute(Phpbb3Manager.SQL_DIS_USER, [email, password, username])
            logger.info(f"Updated phpbb user {username} info")
        except Exception:
            logger.exception(f"Unable to update phpbb user {username} info.")
            pass
