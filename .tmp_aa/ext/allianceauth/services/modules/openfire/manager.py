import logging
import random
import re
import string
from urllib.parse import urlparse

import slixmpp
from ofrestapi import exception
from ofrestapi.users import Users as ofUsers

from django.conf import settings

logger = logging.getLogger(__name__)


class OpenfireManager:
    def __init__(self):
        pass

    @staticmethod
    def __add_address_to_username(username):
        address = urlparse(settings.OPENFIRE_ADDRESS).netloc.split(":")[0]
        completed_username = username + "@" + address
        return completed_username

    @staticmethod
    def __sanitize_username(username):
        # https://xmpp.org/extensions/xep-0106.html#escaping
        replace = [
            ("\\", "\\5c"),  # Escape backslashes first to double escape existing escape sequences
            ("\"", "\\22"),
            ("&", "\\26"),
            ("'", "\\27"),
            ("/", "\\2f"),
            (":", "\\3a"),
            ("<", "\\3c"),
            (">", "\\3e"),
            ("@", "\\40"),
            ("\u007F", ""),
            ("\uFFFE", ""),
            ("\uFFFF", ""),
            (" ", "\\20"),
        ]

        sanitized = username.strip(' ')

        for find, rep in replace:
            sanitized = sanitized.replace(find, rep)

        return sanitized

    @staticmethod
    def __generate_random_pass():
        return ''.join([random.choice(string.ascii_letters + string.digits) for n in range(16)])

    @staticmethod
    def _sanitize_groupname(name):
        name = name.strip(' _').lower()
        return re.sub(r'[^\w.-]', '', name)

    @staticmethod
    def add_user(username):
        logger.debug(f"Adding username {username} to openfire.")
        try:
            sanitized_username = OpenfireManager.__sanitize_username(username)
            password = OpenfireManager.__generate_random_pass()
            api = ofUsers(settings.OPENFIRE_ADDRESS, settings.OPENFIRE_SECRET_KEY)
            api.add_user(sanitized_username, password)
            logger.info(f"Added openfire user {username}")
        except exception.UserAlreadyExistsException:
            # User exist
            logger.error(f"Attempting to add a user {username} to openfire which already exists on server.")
            return "", ""

        return sanitized_username, password

    @staticmethod
    def delete_user(username):
        logger.debug(f"Deleting user {username} from openfire.")
        try:
            api = ofUsers(settings.OPENFIRE_ADDRESS, settings.OPENFIRE_SECRET_KEY)
            api.delete_user(username)
            logger.info(f"Deleted user {username} from openfire.")
            return True
        except exception.UserNotFoundException:
            logger.error(f"Attempting to delete a user {username} from openfire which was not found on server.")
            return False

    @staticmethod
    def lock_user(username):
        logger.debug(f"Locking openfire user {username}")
        api = ofUsers(settings.OPENFIRE_ADDRESS, settings.OPENFIRE_SECRET_KEY)
        api.lock_user(username)
        logger.info(f"Locked openfire user {username}")

    @staticmethod
    def unlock_user(username):
        logger.debug(f"Unlocking openfire user {username}")
        api = ofUsers(settings.OPENFIRE_ADDRESS, settings.OPENFIRE_SECRET_KEY)
        api.unlock_user(username)
        logger.info(f"Unlocked openfire user {username}")

    @staticmethod
    def update_user_pass(username, password=None):
        logger.debug(f"Updating openfire user {username} password.")
        try:
            if not password:
                password = OpenfireManager.__generate_random_pass()
            api = ofUsers(settings.OPENFIRE_ADDRESS, settings.OPENFIRE_SECRET_KEY)
            api.update_user(username, password=password)
            logger.info(f"Updated openfire user {username} password.")
            return password
        except exception.UserNotFoundException:
            logger.error(f"Unable to update openfire user {username} password - user not found on server.")
            return ""

    @classmethod
    def update_user_groups(cls, username, groups):
        logger.debug(f"Updating openfire user {username} groups {groups}")
        s_groups = list(map(cls._sanitize_groupname, groups))  # Sanitized group names
        api = ofUsers(settings.OPENFIRE_ADDRESS, settings.OPENFIRE_SECRET_KEY)
        response = api.get_user_groups(username)
        remote_groups = []
        if response:
            remote_groups = response['groupname']
            if isinstance(remote_groups, str):
                remote_groups = [remote_groups]
        remote_groups = list(map(cls._sanitize_groupname, remote_groups))
        logger.debug(f"Openfire user {username} has groups {remote_groups}")
        add_groups = []
        del_groups = []
        for g in s_groups:
            if g not in remote_groups:
                add_groups.append(g)
        for g in remote_groups:
            if g not in s_groups:
                del_groups.append(g)
        logger.info(
            f"Updating openfire groups for user {username} - adding {add_groups}, removing {del_groups}")
        if add_groups:
            api.add_user_groups(username, add_groups)
        if del_groups:
            api.delete_user_groups(username, del_groups)

    @staticmethod
    def delete_user_groups(username, groups):
        logger.debug(f"Deleting openfire groups {groups} from user {username}")
        api = ofUsers(settings.OPENFIRE_ADDRESS, settings.OPENFIRE_SECRET_KEY)
        api.delete_user_groups(username, groups)
        logger.info(f"Deleted groups {groups} from openfire user {username}")

    @classmethod
    def send_broadcast_message(cls, group_name, broadcast_message):
        s_group_name = cls._sanitize_groupname(group_name)
        logger.debug(f"Sending jabber ping to group {s_group_name} with message {broadcast_message}")
        to_address = s_group_name + '@' + settings.BROADCAST_SERVICE_NAME + '.' + settings.JABBER_URL
        xmpp = PingBot(settings.BROADCAST_USER, settings.BROADCAST_USER_PASSWORD, to_address, broadcast_message)
        xmpp.register_plugin('xep_0030')  # Service Discovery
        xmpp.register_plugin('xep_0199')  # XMPP Ping
        if xmpp.connect(reattempt=False):
            xmpp.process(block=True)
            message = None
            if xmpp.message_sent:
                logger.debug(f"Sent jabber ping to group {group_name}")
                return
            else:
                message = "Failed to send Openfire broadcast message."
            logger.error(message)
            raise PingBotException(message)
        else:
            logger.error("Unable to connect to jabber server")
            raise PingBotException("Unable to connect to jabber server.")


class PingBot(slixmpp.ClientXMPP):
    """
    A copy-paste of the example client bot from
    http://sleekxmpp.com/getting_started/sendlogout.html
    """
    def __init__(self, jid, password, recipient, message):
        slixmpp.ClientXMPP.__init__(self, jid, password)

        self.reconnect_max_attempts = 5
        self.auto_reconnect = False
        # The message we wish to send, and the JID that
        # will receive it.
        self.recipient = recipient
        self.msg = message

        # Success checking
        self.message_sent = False

        # The session_start event will be triggered when
        # the bot establishes its connection with the server
        # and the XML streams are ready for use. We want to
        # listen for this event so that we we can initialize
        # our roster.
        self.add_event_handler("session_start", self.start)
        if getattr(settings, 'BROADCAST_IGNORE_INVALID_CERT', False):
            self.add_event_handler("ssl_invalid_cert", self.discard)

    def discard(self, *args, **kwargs):
        # Discard the event
        return

    def start(self, event):
        self.send_presence()
        self.get_roster()

        self.send_message(mto=self.recipient,
                            mbody=self.msg,
                            mtype='chat')
        self.message_sent = True
        # Using wait=True ensures that the send queue will be
        # emptied before ending the session.
        self.disconnect(wait=True)


class PingBotException(Exception):
    pass
