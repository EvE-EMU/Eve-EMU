"""Settings for Mail Relay."""

from app_utils.app_settings import clean_setting

DISCORDPROXY_HOST = clean_setting("DISCORDPROXY_HOST", "localhost")
"""Port used to communicate with Discord Proxy."""

DISCORDPROXY_PORT = clean_setting("DISCORDPROXY_PORT", 50051)
"""Host used to communicate with Discord Proxy."""

MAILRELAY_DISCORDPROXY_TIMEOUT = clean_setting("MAILRELAY_DISCORDPROXY_TIMEOUT", 30)
"""Timeout for sending request to DISCORDPROXY in seconds."""

MAILRELAY_OLDEST_MAIL_HOURS = clean_setting("MAILRELAY_OLDEST_MAIL_HOURS", 2)
"""Oldest mail to be forwarded in hours. Set to 0 to disable."""

MAILRELAY_RELAY_GRACE_MINUTES = clean_setting("MAILRELAY_RELAY_GRACE_MINUTES", 30)
"""Max time in minutes since last successful relay before service is reported as down."""
