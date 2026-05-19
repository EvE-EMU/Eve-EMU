import datetime as dt
from unittest.mock import patch

from celery import shared_task
from memberaudit.tests.utils import add_memberaudit_character_to_user
from pytz import utc

from django.test import override_settings

from app_utils.testing import NoSocketsTestCase, create_fake_user

from mailrelay.models import RelayConfig
from mailrelay.tasks import forward_new_mails

from .factories import (
    create_character_mail,
    create_eve_entities_from_evecharacter,
    create_eve_entity,
    create_relay_config,
)

MODELS_PATH = "mailrelay.models"
TASKS_PATH = "mailrelay.tasks"


@shared_task
def dummy_task(*args, **kwargs):
    """Can replace tasks that need to run."""
    pass


@override_settings(CELERY_ALWAYS_EAGER=True, CELERY_EAGER_PROPAGATES_EXCEPTIONS=True)
@patch(MODELS_PATH + ".MAILRELAY_OLDEST_MAIL_HOURS", 2)
@patch(MODELS_PATH + ".create_discordproxy_client", spec=True)
@patch(TASKS_PATH + ".update_character_mails", new=dummy_task)
class TestForwardNewMails(NoSocketsTestCase):
    def test_should_forward_mail_with_one_config(self, mock_create_discord_client):
        # given
        user_1001 = create_fake_user(1001, "Bruce Wayne")
        character_1001 = add_memberaudit_character_to_user(user_1001, 1001)
        create_eve_entities_from_evecharacter(
            character_1001.character_ownership.character
        )
        create_eve_entity(id=1002, name="Peter Parker")
        create_character_mail(character=character_1001, sender_id=1002)
        create_relay_config(character=character_1001)

        # when
        with patch(MODELS_PATH + ".now") as mock_now:
            mock_now.return_value = dt.datetime(2021, 12, 24, 12, 30, tzinfo=utc)
            forward_new_mails.delay()

        # then
        self.assertEqual(
            mock_create_discord_client.return_value.create_channel_message.call_count, 1
        )

    def test_should_forward_mail_with_multiple_configs(
        self, mock_create_discord_client
    ):
        # given
        user_1001 = create_fake_user(1001, "Bruce Wayne")
        character_1001 = add_memberaudit_character_to_user(user_1001, 1001)
        create_eve_entities_from_evecharacter(
            character_1001.character_ownership.character
        )
        user_1002 = create_fake_user(1002, "Peter Parker")
        character_1002 = add_memberaudit_character_to_user(user_1002, 1002)
        create_eve_entity(id=1002, name="Peter Parker")
        create_character_mail(character=character_1001, sender_id=1002)
        create_relay_config(character=character_1001)
        create_character_mail(
            character=character_1002, sender_id=1002, recipient_ids=[2001, 1001]
        )
        create_relay_config(
            character=character_1002, mail_category=RelayConfig.MailCategory.CORPORATION
        )
        # when
        with patch(MODELS_PATH + ".now") as mock_now:
            mock_now.return_value = dt.datetime(2021, 12, 24, 12, 30, tzinfo=utc)
            forward_new_mails.delay()
        # then
        self.assertEqual(
            mock_create_discord_client.return_value.create_channel_message.call_count, 2
        )
