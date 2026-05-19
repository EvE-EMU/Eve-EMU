"""Tasks for Mail Relay."""

from celery import chain, shared_task
from discordproxy.exceptions import DiscordProxyException
from memberaudit.models import CharacterMail
from memberaudit.tasks import update_character_mails

from allianceauth.services.hooks import get_extension_logger
from app_utils.logging import LoggerAddTag

from . import __title__
from .models import RelayConfig

logger = LoggerAddTag(get_extension_logger(__name__), __title__)

WAIT_FOR_MAIL_UPDATE_TO_COMPLETE = 60


@shared_task
def forward_new_mails():
    """Forward new mails from all active configs."""
    for config in RelayConfig.objects.filter(is_enabled=True):
        if not config.discord_channel:
            logger.warning("No channel configured for config %s", config)
            continue

        update_character_mails.apply_async(
            kwargs={"character_pk": config.character.pk, "force_update": False}
        )
        forward_new_mails_for_config.apply_async(
            args=[config.pk], countdown=WAIT_FOR_MAIL_UPDATE_TO_COMPLETE
        )


@shared_task
def forward_new_mails_for_config(config_pk: int):
    """Forward new mails from one config."""
    config = RelayConfig.objects.select_related("character").get(pk=config_pk)
    new_mails_qs = config.new_mails_queryset()
    if not new_mails_qs.exists():
        config.record_service_run()
        logger.info("No new mails to forward")
        return

    my_tasks = [
        forward_mail_to_discord.si(config_pk=config_pk, mail_pk=mail.pk)
        for mail in new_mails_qs.order_by("timestamp")
    ]
    my_tasks.append(record_service_run.si(config_pk))
    chain(my_tasks).delay()


@shared_task
def forward_mail_to_discord(config_pk, mail_pk):
    """Forward one mail to Discord."""
    config: RelayConfig = RelayConfig.objects.select_related(
        "character", "discord_channel"
    ).get(pk=config_pk)
    mail: CharacterMail = config.character.mails.get(pk=mail_pk)  # type: ignore
    try:
        config.send_mail(mail=mail)
    except DiscordProxyException as ex:
        logger.error(
            "%s: Failed to send mail %s to channel %s due to error from Discord Proxy. "
            "Will try again later: %s",
            config,
            mail,
            config.discord_channel,
            ex,
        )

    logger.info(
        "%s: Forwarded mail %s to channel %s", config, mail, config.discord_channel
    )


@shared_task
def record_service_run(config_pk):
    """Record completion of successful relay."""
    config = RelayConfig.objects.get(pk=config_pk)
    config.record_service_run()
