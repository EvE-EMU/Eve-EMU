from unittest.mock import patch

from discordproxy.client import DiscordClient

from django.test import TestCase

from mailrelay.providers import create_discordproxy_client


@patch("mailrelay.providers.DISCORDPROXY_HOST", "1.2.3.4")
@patch("mailrelay.providers.DISCORDPROXY_PORT", "56789")
@patch("mailrelay.providers.MAILRELAY_DISCORDPROXY_TIMEOUT", 42)
class TestCreateDiscordproxyClient(TestCase):
    def test_should_return_client(self):
        r = create_discordproxy_client()
        self.assertIsInstance(r, DiscordClient)
        self.assertEqual(r.target, "1.2.3.4:56789")
        self.assertEqual(r.timeout, 42)
