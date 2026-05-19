import datetime

from allianceauth.services.hooks import get_extension_logger
from django.db.models.signals import post_save, pre_delete
from django.dispatch import receiver
from django.utils import timezone
from esi.clients import EsiClientProvider

from .app_settings import (
    OPCALENDAR_NOTIFY_IMPORTS,
    OPCALENDAR_NOTIFY_REPEAT_EVENTS,
    get_site_url,
)
from .models import Event, IngameEvents

logger = get_extension_logger(__name__)

RED = 16711710
BLUE = 42751
GREEN = 6684416

esi = EsiClientProvider()


def send_webhook(embed, hook, eve_time):
    """Helper function to send the webhook."""
    old = datetime.datetime.now(timezone.utc) > eve_time
    if hook and hook.webhook and hook.webhook.enabled:
        if old and hook.ignore_past_fleets:
            logger.debug("Event is in the past, not sending webhook.")
        else:
            hook.webhook.send_embed(embed)


@receiver(post_save, sender=Event)
@receiver(post_save, sender=IngameEvents)
def fleet_saved(sender, instance, created, **kwargs):
    logger.debug("A new operation has been scheduled: %s", instance)
    col = GREEN if created else BLUE

    if sender == IngameEvents and OPCALENDAR_NOTIFY_IMPORTS:
        handle_ingame_event(instance, created, col)
    elif sender == Event:
        handle_standard_event(instance, created, col)


def handle_ingame_event(instance, created, col):
    """Handle IngameEvents notifications."""
    try:
        logger.debug("New signal created for Ingame Calendar Event: %s", instance.title)
        url = get_site_url() + f"/opcalendar/ingame/event/{instance.pk}/details/"
        message = f"New ingame calendar event: {instance.title}"
        entity_id = esi.client.Search.get_search(
            categories=[instance.owner_type], search=instance.owner_name, strict=True
        ).results()[instance.owner_type][0]

        logger.debug("Entity data is %s", entity_id)
        portrait, ticker = get_entity_details(entity_id, instance.owner_type)

        embed = {
            "title": message,
            "description": instance.text,
            "url": url,
            "color": col,
            "fields": [
                {"name": "Owner", "value": instance.owner_name, "inline": True},
                {
                    "name": "Eve Time",
                    "value": instance.event_start_date.strftime("%Y-%m-%d %H:%M:%S"),
                },
            ],
            "footer": {"icon_url": portrait, "text": f"{instance.owner_name} {ticker}"},
        }
        send_webhook(embed, instance.owner.event_visibility, instance.event_start_date)
    except Exception as e:
        logger.exception(e)


def handle_standard_event(instance, created, col):
    """Handle standard Event notifications."""
    if instance.repeat_event and OPCALENDAR_NOTIFY_REPEAT_EVENTS:
        handle_event_notification(instance, created, col, "New event:")
    elif not instance.repeat_event:
        handle_event_notification(instance, created, col, "New event:")


def handle_event_notification(instance, created, col, message_prefix):
    """Generate and send event notifications."""
    try:
        logger.debug("New signal fleet created for event %s", instance.title)
        url = get_site_url() + f"/opcalendar/event/{instance.pk}/details/"
        message = f"{message_prefix} {instance.title}"

        main_char = instance.eve_character
        if main_char:
            portrait = main_char.portrait_url_64
            character_name = main_char.character_name
            ticker = f"[{main_char.corporation_ticker}]"
        else:
            portrait = character_name = ticker = ""

        embed = {
            "title": message,
            "description": instance.description,
            "url": url,
            "color": col,
            "fields": [
                {"name": "FC", "value": instance.fc, "inline": True},
                {"name": "Type", "value": instance.operation_type.name, "inline": True},
                {"name": "Formup", "value": instance.formup_system, "inline": True},
                {
                    "name": "Eve Time",
                    "value": instance.start_time.strftime("%Y-%m-%d %H:%M:%S"),
                },
            ],
            "footer": {
                "icon_url": portrait,
                "text": f"{character_name} {ticker}, {instance.host}",
            },
        }
        send_webhook(embed, instance.event_visibility, instance.start_time)
    except Exception as e:
        logger.exception(e)


def get_entity_details(entity_id, owner_type):
    """Retrieve the entity details based on the owner type."""
    if owner_type == "alliance":
        portrait = f"https://images.evetech.net/alliances/{entity_id}/logo"
        ticker = f"[{esi.client.Alliance.get_alliances_alliance_id(alliance_id=entity_id).results()['ticker']}]"
    elif owner_type == "corporation":
        portrait = f"https://images.evetech.net/corporations/{entity_id}/logo"
        ticker = f"[{esi.client.Corporation.get_corporations_corporation_id(corporation_id=entity_id).results()['ticker']}]"
    else:  # character
        portrait = f"https://images.evetech.net/characters/{entity_id}/portrait"
        ticker = ""
    return portrait, ticker


@receiver(pre_delete, sender=Event)
@receiver(pre_delete, sender=IngameEvents)
def fleet_deleted(sender, instance, **kwargs):
    logger.debug("An operation has been deleted: %s", instance)

    if sender == IngameEvents and OPCALENDAR_NOTIFY_IMPORTS:
        handle_event_deletion(instance, "Deleted Ingame Calendar Event:", RED)
    elif sender == Event:
        handle_event_deletion(instance, "Event deleted:", RED)


def handle_event_deletion(instance, message_prefix, color):
    """Handle event deletions and send notifications."""
    try:
        url = get_site_url() + f"/opcalendar/event/{instance.pk}/details/"
        message = f"{message_prefix} {instance.title}"

        main_char = instance.eve_character
        if main_char:
            portrait = main_char.portrait_url_64
            character_name = main_char.character_name
            ticker = f"[{main_char.corporation_ticker}]"
        else:
            portrait = character_name = ticker = ""

        embed = {
            "title": message,
            "description": instance.description,
            "url": url,
            "color": color,
            "fields": [
                {"name": "FC", "value": instance.fc, "inline": True},
                {"name": "Type", "value": instance.operation_type.name, "inline": True},
                {"name": "Formup", "value": instance.formup_system, "inline": True},
                {
                    "name": "Eve Time",
                    "value": instance.start_time.strftime("%Y-%m-%d %H:%M:%S"),
                },
            ],
            "footer": {
                "icon_url": portrait,
                "text": f"{character_name} {ticker}, {instance.host}",
            },
        }
        send_webhook(embed, instance.event_visibility, instance.start_time)
    except Exception as e:
        logger.exception(e)
