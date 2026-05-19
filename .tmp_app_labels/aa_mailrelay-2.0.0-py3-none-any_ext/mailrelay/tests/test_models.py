import datetime as dt
from unittest.mock import patch

from discordproxy.client import Channel
from memberaudit.tests.utils import add_memberaudit_character_to_user
from pytz import utc

from app_utils.testing import NoSocketsTestCase, create_fake_user

from mailrelay.models import DiscordCategory, DiscordChannel, RelayConfig

from .factories import (
    create_character_mail,
    create_discord_category,
    create_discord_channel,
    create_discordproxy_channel,
    create_eve_entities_from_evecharacter,
    create_eve_entity,
    create_relay_config,
)

MODELS_PATH = "mailrelay.models"
MANAGERS_PATH = "mailrelay.managers"


class TestRelayConfigNewMailsQueryset(NoSocketsTestCase):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        user = create_fake_user(1001, "Bruce Wayne")
        cls.character = add_memberaudit_character_to_user(user, 1001)
        create_eve_entities_from_evecharacter(cls.character.eve_character)
        create_eve_entity(id=1002, name="Peter Parker")

    @patch(MODELS_PATH + ".MAILRELAY_OLDEST_MAIL_HOURS", 2)
    def test_should_return_corporation_mails_only(self):
        # given
        corporation_mail = create_character_mail(
            character=self.character, sender_id=1002, recipient_ids=[2001]
        )
        create_character_mail(character=self.character, sender_id=1002)
        create_character_mail(
            character=self.character, sender_id=1002, recipient_ids=[3001]
        )
        config = create_relay_config(
            character=self.character, mail_category=RelayConfig.MailCategory.CORPORATION
        )

        # when
        with patch(MODELS_PATH + ".now") as mock_now:
            mock_now.return_value = dt.datetime(2021, 12, 24, 12, 30, tzinfo=utc)
            result = config.new_mails_queryset()

        # then
        mail_pks = set(result.values_list("pk", flat=True))
        self.assertSetEqual(mail_pks, {corporation_mail.pk})

    @patch(MODELS_PATH + ".MAILRELAY_OLDEST_MAIL_HOURS", 2)
    def test_should_return_alliance_mails_only(self):
        # given
        alliance_mail = create_character_mail(
            character=self.character, sender_id=1002, recipient_ids=[3001]
        )
        create_character_mail(character=self.character, sender_id=1002)
        create_character_mail(
            character=self.character, sender_id=1002, recipient_ids=[2001]
        )
        config = create_relay_config(
            character=self.character, mail_category=RelayConfig.MailCategory.ALLIANCE
        )

        # when
        with patch(MODELS_PATH + ".now") as mock_now:
            mock_now.return_value = dt.datetime(2021, 12, 24, 12, 30, tzinfo=utc)
            result = config.new_mails_queryset()

        # then
        mail_pks = set(result.values_list("pk", flat=True))
        self.assertSetEqual(mail_pks, {alliance_mail.pk})

    @patch(MODELS_PATH + ".MAILRELAY_OLDEST_MAIL_HOURS", 2)
    def test_should_not_return_alliance_mails(self):
        # given
        user = create_fake_user(1003, "Clark Kent", 2009, "Wayne Food", "WYF")
        character = add_memberaudit_character_to_user(user, 1003)
        character.eve_character.alliance_id = None
        character.eve_character.alliance_name = ""
        character.eve_character.save()
        create_eve_entities_from_evecharacter(character.eve_character)
        create_character_mail(character=character, sender_id=1002, recipient_ids=[3001])
        create_character_mail(character=character, sender_id=1002)
        create_character_mail(character=character, sender_id=1002, recipient_ids=[2001])
        config = create_relay_config(
            character=character, mail_category=RelayConfig.MailCategory.ALLIANCE
        )

        # when
        with patch(MODELS_PATH + ".now") as mock_now:
            mock_now.return_value = dt.datetime(2021, 12, 24, 12, 30, tzinfo=utc)
            result = config.new_mails_queryset()

        # then
        mail_pks = set(result.values_list("pk", flat=True))
        self.assertSetEqual(mail_pks, set())

    @patch(MODELS_PATH + ".MAILRELAY_OLDEST_MAIL_HOURS", 2)
    def test_should_return_all_mails(self):
        # given
        corporation_mail = create_character_mail(
            character=self.character, sender_id=1002, recipient_ids=[2001]
        )
        personal_mail = create_character_mail(character=self.character, sender_id=1002)
        alliance_mail = create_character_mail(
            character=self.character, sender_id=1002, recipient_ids=[3001]
        )
        config = create_relay_config(
            character=self.character, mail_category=RelayConfig.MailCategory.ALL
        )

        # when
        with patch(MODELS_PATH + ".now") as mock_now:
            mock_now.return_value = dt.datetime(2021, 12, 24, 12, 30, tzinfo=utc)
            result = config.new_mails_queryset()

        # then
        mail_pks = set(result.values_list("pk", flat=True))
        self.assertSetEqual(
            mail_pks, {corporation_mail.pk, personal_mail.pk, alliance_mail.pk}
        )

    @patch(MODELS_PATH + ".MAILRELAY_OLDEST_MAIL_HOURS", 1)
    def test_should_not_return_old_mails(self):
        # given
        new_mail = create_character_mail(
            character=self.character,
            sender_id=1002,
            timestamp=dt.datetime(2021, 12, 24, 11, 30, tzinfo=utc),
        )
        create_character_mail(
            character=self.character,
            sender_id=1002,
            timestamp=dt.datetime(2021, 12, 24, 11, 00, tzinfo=utc),
        )
        config = create_relay_config(
            character=self.character, mail_category=RelayConfig.MailCategory.ALL
        )

        # when
        with patch(MODELS_PATH + ".now") as mock_now:
            mock_now.return_value = dt.datetime(2021, 12, 24, 12, 29, tzinfo=utc)
            result = config.new_mails_queryset()

        # then
        mail_pks = set(result.values_list("pk", flat=True))
        self.assertSetEqual(mail_pks, {new_mail.pk})

    @patch(MODELS_PATH + ".MAILRELAY_OLDEST_MAIL_HOURS", 0)
    def test_should_return_all_mail_when_setting_disabled(self):
        # given
        new_mail = create_character_mail(
            character=self.character,
            sender_id=1002,
            timestamp=dt.datetime(2021, 12, 24, 11, 30, tzinfo=utc),
        )
        old_mail = create_character_mail(
            character=self.character,
            sender_id=1002,
            timestamp=dt.datetime(2021, 12, 24, 11, 00, tzinfo=utc),
        )
        config = create_relay_config(
            character=self.character, mail_category=RelayConfig.MailCategory.ALL
        )

        # when
        with patch(MODELS_PATH + ".now") as mock_now:
            mock_now.return_value = dt.datetime(2021, 12, 24, 12, 29, tzinfo=utc)
            result = config.new_mails_queryset()

        # then
        mail_pks = set(result.values_list("pk", flat=True))
        self.assertSetEqual(mail_pks, {old_mail.pk, new_mail.pk})


@patch(MODELS_PATH + ".create_discordproxy_client", spec=True)
class TestRelayConfigSendMail(NoSocketsTestCase):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        user = create_fake_user(1001, "Bruce Wayne")
        cls.character = add_memberaudit_character_to_user(user, 1001)
        create_eve_entities_from_evecharacter(cls.character.eve_character)
        create_eve_entity(id=1002, name="Peter Parker")

    def test_should_send_valid_mail(self, mock_create_discord_client):
        # given
        mail = create_character_mail(character=self.character, sender_id=1002)
        config = create_relay_config(character=self.character)
        # when
        config.send_mail(mail)
        # then
        self.assertTrue(
            mock_create_discord_client.return_value.create_channel_message.called
        )

    def test_should_not_send_mail_without_body(self, mock_create_discord_client):
        # given
        mail = create_character_mail(character=self.character, sender_id=1002, body="")
        config = create_relay_config(character=self.character)
        # when
        config.send_mail(mail)
        # then
        self.assertFalse(
            mock_create_discord_client.return_value.create_channel_message.called
        )

    def test_should_send_mail_with_everybody_ping(self, mock_create_discord_client):
        # given
        mail = create_character_mail(character=self.character, sender_id=1002)
        config = create_relay_config(
            character=self.character, ping_type=RelayConfig.ChannelPingType.EVERYONE
        )
        # when
        config.send_mail(mail)
        # then
        (
            _,
            kwargs,
        ) = mock_create_discord_client.return_value.create_channel_message.call_args
        self.assertIn("@everyone", kwargs["content"])


class TestRelayConfigOther(NoSocketsTestCase):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        user = create_fake_user(1001, "Bruce Wayne")
        cls.character = add_memberaudit_character_to_user(user, 1001)

    def test_should_record_service_run(self):
        config = create_relay_config(character=self.character)
        my_now = dt.datetime(2021, 12, 24, 12, 30, tzinfo=utc)
        # when
        with patch(MODELS_PATH + ".now") as mock_now:
            mock_now.return_value = my_now
            config.record_service_run()
        # then
        config.refresh_from_db()
        self.assertAlmostEqual(
            config.last_service_run_at, my_now, delta=dt.timedelta(seconds=30)
        )

    @patch(MODELS_PATH + ".MAILRELAY_RELAY_GRACE_MINUTES", 30)
    def test_should_report_as_up(self):
        config = create_relay_config(
            character=self.character,
            last_service_run_at=dt.datetime(2021, 12, 24, 12, 15, tzinfo=utc),
        )
        # when
        with patch(MODELS_PATH + ".now") as mock_now:
            mock_now.return_value = dt.datetime(2021, 12, 24, 12, 30, tzinfo=utc)
            result = config.is_service_up
        # then
        self.assertTrue(result)

    @patch(MODELS_PATH + ".MAILRELAY_RELAY_GRACE_MINUTES", 30)
    def test_should_report_as_down_1(self):
        config = create_relay_config(
            character=self.character,
            last_service_run_at=dt.datetime(2021, 12, 24, 11, 55, tzinfo=utc),
        )
        # when
        with patch(MODELS_PATH + ".now") as mock_now:
            mock_now.return_value = dt.datetime(2021, 12, 24, 12, 30, tzinfo=utc)
            result = config.is_service_up
        # then
        self.assertFalse(result)

    @patch(MODELS_PATH + ".MAILRELAY_RELAY_GRACE_MINUTES", 30)
    def test_should_report_as_down_2(self):
        config = create_relay_config(character=self.character, last_service_run_at=None)
        # when
        with patch(MODELS_PATH + ".now") as mock_now:
            mock_now.return_value = dt.datetime(2021, 12, 24, 12, 30, tzinfo=utc)
            result = config.is_service_up
        # then
        self.assertIsNone(result)


@patch(MANAGERS_PATH + ".create_discordproxy_client", spec=True)
class TestDiscordChannelManager(NoSocketsTestCase):
    def test_should_create_new_channels_and_categories(
        self, mock_create_discord_client
    ):
        # given
        mock_create_discord_client.return_value.get_guild_channels.return_value = [
            create_discordproxy_channel(id=1, name="alpha"),
            create_discordproxy_channel(id=2, name="bravo", parent_id=3),
            create_discordproxy_channel(
                id=3, name="zulu", type=Channel.Type.GUILD_CATEGORY
            ),
        ]
        # when
        result = DiscordChannel.objects.sync()
        # then
        self.assertEqual(result, 2)
        self.assertEqual(DiscordChannel.objects.count(), 2)
        obj = DiscordChannel.objects.get(id=1)
        self.assertEqual(obj.name, "alpha")
        self.assertIsNone(obj.category)
        obj = DiscordChannel.objects.get(id=2)
        self.assertEqual(obj.name, "bravo")
        self.assertEqual(obj.category.name, "zulu")

    def test_should_update_existing_channels_and_categories(
        self, mock_create_discord_client
    ):
        # given
        mock_create_discord_client.return_value.get_guild_channels.return_value = [
            create_discordproxy_channel(id=1, name="alpha"),
            create_discordproxy_channel(id=2, name="bravo", parent_id=3),
            create_discordproxy_channel(
                id=3, name="zulu", type=Channel.Type.GUILD_CATEGORY
            ),
        ]
        create_discord_channel(id=1, name="update-me")
        create_discord_category(id=3, name="update-me")
        # when
        result = DiscordChannel.objects.sync()
        # then
        self.assertEqual(result, 2)
        self.assertEqual(DiscordChannel.objects.count(), 2)
        obj = DiscordChannel.objects.get(id=1)
        self.assertEqual(obj.name, "alpha")
        obj = DiscordChannel.objects.get(id=2)
        self.assertEqual(obj.name, "bravo")
        obj = DiscordCategory.objects.get(id=3)
        self.assertEqual(obj.name, "zulu")

    def test_should_remove_obsolete_channels_and_categories(
        self, mock_create_discord_client
    ):
        # given
        mock_create_discord_client.return_value.get_guild_channels.return_value = [
            create_discordproxy_channel(id=1, name="alpha"),
            create_discordproxy_channel(id=2, name="bravo"),
        ]
        create_discord_channel(id=3, name="delete-me")
        create_discord_category(id=4, name="delete-me")
        # when
        result = DiscordChannel.objects.sync()
        # then
        self.assertEqual(result, 2)
        self.assertEqual(DiscordChannel.objects.count(), 2)
        obj = DiscordChannel.objects.get(id=1)
        self.assertEqual(obj.name, "alpha")
        obj = DiscordChannel.objects.get(id=2)
        self.assertEqual(obj.name, "bravo")
        self.assertFalse(DiscordCategory.objects.filter(id=4).exists())
