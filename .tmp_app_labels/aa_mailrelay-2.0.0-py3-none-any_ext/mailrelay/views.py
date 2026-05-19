"""Views for Mail Relay."""

from discordproxy.exceptions import DiscordProxyException

from django.contrib import messages
from django.contrib.admin.views.decorators import staff_member_required
from django.contrib.auth.decorators import login_required
from django.shortcuts import redirect

from allianceauth.services.hooks import get_extension_logger
from app_utils.logging import LoggerAddTag

from . import __title__
from .models import DiscordChannel

logger = LoggerAddTag(get_extension_logger(__name__), __title__)


@login_required
@staff_member_required
def admin_update_discord_channels(request):
    """View to update the discord channels."""
    try:
        channels_count = DiscordChannel.objects.sync()
        messages.success(
            request, f"Successfully updated {channels_count} channels from Discord."
        )
    except DiscordProxyException as ex:
        logger.error("Failed to fetch channels from Discord", exc_info=True)
        messages.warning(request, f"Failed to fetch channels from Discord: {ex}")
    return redirect("admin:mailrelay_relayconfig_changelist")
