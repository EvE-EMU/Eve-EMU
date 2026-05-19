from unittest.mock import patch

from discordproxy.exceptions import DiscordProxyException
from memberaudit.tests.utils import add_memberaudit_character_to_user

from django.contrib.admin.sites import AdminSite
from django.test import TestCase
from django.utils.timezone import now

from app_utils.testing import create_fake_user

from mailrelay.admin import RelayConfigAdmin
from mailrelay.models import RelayConfig

from .factories import (
    create_character_mail,
    create_discord_category,
    create_discord_channel,
    create_eve_entities_from_evecharacter,
    create_eve_entity,
    create_fake_request,
    create_relay_config,
    create_superuser,
)

ADMIN_PATH = "mailrelay.admin"
MODELS_PATH = "mailrelay.models"


@patch(MODELS_PATH + ".MAILRELAY_OLDEST_MAIL_HOURS", 2)
class TestRelayConfigAdmin(TestCase):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.modeladmin = RelayConfigAdmin(model=RelayConfig, admin_site=AdminSite())
        cls.admin_user = create_superuser(username="Clark Kent")
        cls.user = create_fake_user(1001, "Bruce Wayne")
        cls.character = add_memberaudit_character_to_user(cls.user, 1001)

    def test_channel_normal(self):
        # given
        category = create_discord_category(name="Gotham")
        channel = create_discord_channel(name="City Hall", category=category)
        config = create_relay_config(character=self.character, discord_channel=channel)
        # when
        result = self.modeladmin._channel(config)
        # then
        self.assertEqual(result, "Gotham / City Hall")

    def test_channel_empty(self):
        # given
        config = create_relay_config(character=self.character, discord_channel=None)
        # when
        result = self.modeladmin._channel(config)
        # then
        self.assertIn("Error", result)

    def test_organization(self):
        # given
        config = create_relay_config(character=self.character)
        # when
        result = self.modeladmin._organization(config)
        # then
        self.assertEqual(result, "Wayne Technologies Inc.<br>Wayne Enterprises")

    @patch(ADMIN_PATH + ".RelayConfigAdmin.message_user")
    @patch(ADMIN_PATH + ".create_discordproxy_client")
    def test_action_send_test_message(
        self, mock_create_discord_client, mock_message_user
    ):
        # given
        config = create_relay_config(character=self.character)
        request = create_fake_request(user=self.admin_user)
        queryset = RelayConfig.objects.all()
        # when
        self.modeladmin.send_test_message(request, queryset)
        # then
        channel_ids = {
            obj[1]["channel_id"]
            for obj in mock_create_discord_client.return_value.create_channel_message.call_args_list
        }
        self.assertSetEqual(channel_ids, {config.discord_channel.pk})
        self.assertTrue(mock_message_user.called)

    @patch(ADMIN_PATH + ".RelayConfigAdmin.message_user", spec=True)
    @patch(ADMIN_PATH + ".create_discordproxy_client", spec=True)
    def test_action_send_test_message_with_error(
        self, mock_create_discord_client, mock_message_user
    ):
        # given
        mock_create_discord_client.return_value.create_channel_message.side_effect = (
            DiscordProxyException
        )
        create_relay_config(character=self.character)
        request = create_fake_request(user=self.admin_user)
        queryset = RelayConfig.objects.all()
        # when
        self.modeladmin.send_test_message(request, queryset)
        # then
        self.assertTrue(mock_message_user.called)

    def test_should_open_new_change_view(self):
        # given
        create_discord_channel(name="City Hall")
        self.client.force_login(self.admin_user)
        # when
        response = self.client.get("/admin/mailrelay/relayconfig/")
        # then
        self.assertEqual(response.status_code, 200)

    @patch(ADMIN_PATH + ".RelayConfigAdmin.message_user")
    @patch(ADMIN_PATH + ".RelayConfig.send_mail")
    def test_action_resent_mails_should_sent(self, mock_send_mail, mock_message_user):
        # given
        create_eve_entities_from_evecharacter(self.character.eve_character)
        create_eve_entity(id=1002, name="Peter Parker")
        create_character_mail(character=self.character, sender_id=1002, timestamp=now())
        create_relay_config(character=self.character)
        request = create_fake_request(user=self.admin_user)
        queryset = RelayConfig.objects.all()
        # when
        self.modeladmin.resent_mails(request, queryset)
        # then
        self.assertEqual(mock_send_mail.call_count, 1)
        self.assertTrue(mock_message_user.called)
        _, kwargs = mock_message_user.call_args
        self.assertNotIn("level", kwargs)

    @patch(ADMIN_PATH + ".RelayConfigAdmin.message_user")
    @patch(ADMIN_PATH + ".RelayConfig.send_mail")
    def test_action_resent_mails_should_sent_should_handle_error(
        self, mock_send_mail, mock_message_user
    ):
        # given
        mock_send_mail.side_effect = DiscordProxyException
        create_eve_entities_from_evecharacter(self.character.eve_character)
        create_eve_entity(id=1002, name="Peter Parker")
        create_character_mail(character=self.character, sender_id=1002, timestamp=now())
        create_relay_config(character=self.character)
        request = create_fake_request(user=self.admin_user)
        queryset = RelayConfig.objects.all()
        # when
        self.modeladmin.resent_mails(request, queryset)
        # then
        self.assertEqual(mock_send_mail.call_count, 1)
        self.assertTrue(mock_message_user.called)
        _, kwargs = mock_message_user.call_args
        self.assertEqual(kwargs["level"], "WARNING")
