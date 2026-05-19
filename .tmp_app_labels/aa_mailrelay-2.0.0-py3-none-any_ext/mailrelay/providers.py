"""Providers for Mail Relay."""

from discordproxy.client import DiscordClient

from .app_settings import (
    DISCORDPROXY_HOST,
    DISCORDPROXY_PORT,
    MAILRELAY_DISCORDPROXY_TIMEOUT,
)


def create_discordproxy_client() -> DiscordClient:
    """Return client from discordproxy configured for Mail Relay."""
    return DiscordClient(
        target=f"{DISCORDPROXY_HOST}:{DISCORDPROXY_PORT}",
        timeout=MAILRELAY_DISCORDPROXY_TIMEOUT,
    )
