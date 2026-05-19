import datetime as dt
from unittest.mock import patch

from discordproxy.exceptions import DiscordProxyTimeoutError, GrpcStatusCode
from memberaudit.tests.utils import add_memberaudit_character_to_user
from pytz import utc

from django.test import override_settings

from app_utils.testing import NoSocketsTestCase, create_fake_user

from mailrelay.tasks import (
    forward_mail_to_discord,
    forward_new_mails,
    forward_new_mails_for_config,
)

from .factories import (
    create_character_mail,
    create_eve_entities_from_evecharacter,
    create_eve_entity,
    create_relay_config,
)

MODELS_PATH = "mailrelay.models"
TASKS_PATH = "mailrelay.tasks"


@override_settings(CELERY_ALWAYS_EAGER=True, CELERY_EAGER_PROPAGATES_EXCEPTIONS=True)
@patch(MODELS_PATH + ".MAILRELAY_OLDEST_MAIL_HOURS", 2)
@patch(TASKS_PATH + ".update_character_mails", spec=True)
@patch(TASKS_PATH + ".forward_new_mails_for_config", spec=True)
class TestForwardNewMailsAllConfigs(NoSocketsTestCase):
    def test_should_send_mails(
        self, mock_forward_new_mails_for_config, mock_update_character_mails
    ):
        # given
        user_1001 = create_fake_user(1001, "Bruce Wayne")
        character_1001 = add_memberaudit_character_to_user(user_1001, 1001)
        config_1001 = create_relay_config(character=character_1001)
        user_1002 = create_fake_user(1002, "Peter Parker")
        character_1002 = add_memberaudit_character_to_user(user_1002, 1002)
        config_1002 = create_relay_config(character=character_1002)
        user_1003 = create_fake_user(1003, "Clark Kent")
        character_1003 = add_memberaudit_character_to_user(user_1003, 1003)
        create_relay_config(character=character_1003, is_enabled=False)
        # when
        forward_new_mails()
        # then
        self.assertEqual(mock_update_character_mails.apply_async.call_count, 2)
        self.assertEqual(mock_forward_new_mails_for_config.apply_async.call_count, 2)
        called_config_pks = {
            o[1]["args"][0]
            for o in mock_forward_new_mails_for_config.apply_async.call_args_list
        }
        self.assertSetEqual({config_1001.pk, config_1002.pk}, called_config_pks)


@override_settings(CELERY_ALWAYS_EAGER=True, CELERY_EAGER_PROPAGATES_EXCEPTIONS=True)
@patch(MODELS_PATH + ".MAILRELAY_OLDEST_MAIL_HOURS", 2)
@patch(MODELS_PATH + ".RelayConfig.send_mail")
class TestForwardNewMailsOneConfig(NoSocketsTestCase):
    def test_should_forward_all_mails(self, mock_send_mail):
        # given
        mock_send_mail.return_value = True
        user = create_fake_user(1001, "Bruce Wayne")
        character = add_memberaudit_character_to_user(user, 1001)
        create_eve_entities_from_evecharacter(character.eve_character)
        create_eve_entity(id=1002, name="Peter Parker")
        mail_1 = create_character_mail(
            character=character, sender_id=1002, recipient_ids=[2001]
        )
        mail_2 = create_character_mail(character=character, sender_id=1002)
        config = create_relay_config(character=character)
        # when
        with patch(MODELS_PATH + ".now") as mock_now:
            mock_now.return_value = dt.datetime(2021, 12, 24, 12, 30, tzinfo=utc)
            forward_new_mails_for_config(config_pk=config.pk)
        # then
        config.refresh_from_db()
        mails_pk = {call[1]["mail"].pk for call in mock_send_mail.call_args_list}
        self.assertSetEqual(mails_pk, {mail_1.pk, mail_2.pk})
        self.assertIsNotNone(config.last_service_run_at)

    def test_handle_no_new_mails(self, mock_send_mail):
        # given
        mock_send_mail.return_value = True
        user = create_fake_user(1001, "Bruce Wayne")
        character = add_memberaudit_character_to_user(user, 1001)
        create_eve_entities_from_evecharacter(character.eve_character)
        create_eve_entity(id=1002, name="Peter Parker")
        mail = create_character_mail(character=character, sender_id=1002)
        config = create_relay_config(character=character)
        config.mails_sent.add(mail)
        # when
        with patch(MODELS_PATH + ".now") as mock_now:
            mock_now.return_value = dt.datetime(2021, 12, 24, 12, 30, tzinfo=utc)
            forward_new_mails_for_config(config_pk=config.pk)
        # then
        config.refresh_from_db()
        mails_pk = {call[1]["mail"].pk for call in mock_send_mail.call_args_list}
        self.assertSetEqual(mails_pk, set())
        self.assertIsNotNone(config.last_service_run_at)


@patch(MODELS_PATH + ".MAILRELAY_OLDEST_MAIL_HOURS", 2)
@patch(MODELS_PATH + ".RelayConfig.send_mail")
class TestForwardMailToDiscord(NoSocketsTestCase):
    def test_should_send_mail(self, mock_send_mail):
        # given
        mock_send_mail.return_value = True
        user = create_fake_user(1001, "Bruce Wayne")
        character = add_memberaudit_character_to_user(user, 1001)
        create_eve_entities_from_evecharacter(character.eve_character)
        create_eve_entity(id=1002, name="Peter Parker")
        mail = create_character_mail(character=character, sender_id=1002)
        config = create_relay_config(character=character)
        # when
        forward_mail_to_discord(config_pk=config.pk, mail_pk=mail.pk)
        # then
        self.assertEqual(mock_send_mail.call_count, 1)
        _, kwargs = mock_send_mail.call_args
        self.assertEqual(kwargs["mail"], mail)

    def test_should_handle_discord_error(self, mock_send_mail):
        # given
        my_error = DiscordProxyTimeoutError(
            status=GrpcStatusCode.DEADLINE_EXCEEDED, details="test"
        )
        mock_send_mail.side_effect = my_error
        user = create_fake_user(1001, "Bruce Wayne")
        character = add_memberaudit_character_to_user(user, 1001)
        create_eve_entities_from_evecharacter(character.eve_character)
        create_eve_entity(id=1002, name="Peter Parker")
        mail = create_character_mail(character=character, sender_id=1002)
        config = create_relay_config(character=character)
        # when
        forward_mail_to_discord(config_pk=config.pk, mail_pk=mail.pk)
        # then
        pass
