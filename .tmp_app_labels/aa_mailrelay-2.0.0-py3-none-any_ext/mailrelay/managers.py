"""Managers for Mail Relay."""

from discordproxy.client import Channel

from django.conf import settings
from django.db import models

from .providers import create_discordproxy_client


class DiscordChannelManager(models.Manager):
    """Manager for DiscordChannel."""

    def sync(self) -> int:
        """Synchronize list of guild channels objects with the Discord server.

        Args:
        - timeout: timeout for request to Discord in seconds

        Returns:
        number of channels
        """
        from .models import DiscordCategory

        try:
            guild_id = int(settings.DISCORD_GUILD_ID)
        except AttributeError:
            raise ValueError(
                "Can not find Discord guild ID in settings. "
                "Is the Discord service configured?"
            ) from None
        client = create_discordproxy_client()
        channels = client.get_guild_channels(guild_id)
        # pylint: disable=no-member
        categories = {
            obj.id: obj for obj in channels if obj.type == Channel.Type.GUILD_CATEGORY
        }
        for category in categories.values():
            DiscordCategory.objects.update_or_create(
                id=category.id, defaults={"name": category.name}
            )
        channel_ids = set()
        # pylint: disable=no-member
        text_channels = [obj for obj in channels if obj.type == Channel.Type.GUILD_TEXT]
        for channel in text_channels:
            if channel.parent_id and channel.parent_id in categories:
                category_id = channel.parent_id
            else:
                category_id = None
            self.update_or_create(
                id=channel.id,
                defaults={"name": channel.name, "category_id": category_id},
            )
            channel_ids.add(channel.id)
        self.exclude(id__in=channel_ids).delete()
        DiscordCategory.objects.filter(channels__isnull=True).delete()
        return len(text_channels)
