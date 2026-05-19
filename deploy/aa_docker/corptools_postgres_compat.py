"""PostgreSQL-compatible CharacterAudit.get_oldest_qs for allianceauth-corptools on AA 5."""

from __future__ import annotations

import datetime
import logging

from django.db import connection
from django.db import models
from django.db.models import ExpressionWrapper, F, FloatField, Func
from django.db.models.functions import Extract
from django.utils import timezone

logger = logging.getLogger(__name__)


def _timestamp_to_epoch(field_name: str):
    if connection.vendor == "postgresql":
        return Extract(field_name, "epoch")
    return Func(F(field_name), function="UNIX_TIMESTAMP")


def _epoch_to_datetime(expr):
    if connection.vendor == "postgresql":
        return Func(
            ExpressionWrapper(expr, output_field=FloatField()),
            function="to_timestamp",
            output_field=models.DateTimeField(),
        )

    return Func(
        ExpressionWrapper(expr, output_field=models.BigIntegerField()),
        function="FROM_UNIXTIME",
        output_field=models.DateTimeField(),
    )


def patch_corptools_for_postgresql() -> None:
    if connection.vendor != "postgresql":
        return

    from corptools import app_settings
    from corptools.models.audits import CharacterAudit, CorptoolsConfiguration

    @classmethod
    def get_oldest_qs(cls):
        time_ref = timezone.now() - datetime.timedelta(
            days=app_settings.CT_CHAR_MAX_INACTIVE_DAYS * 3
        )

        ct_conf = CorptoolsConfiguration.get_solo()
        qs = []

        if app_settings.CT_CHAR_ASSETS_MODULE and not (
            app_settings.CT_CHAR_ACTIVE_IGNORE_ASSETS_MODULE
            or ct_conf.disable_update_assets
        ):
            qs.append(_timestamp_to_epoch("last_update_assets"))

        if app_settings.CT_CHAR_CLONES_MODULE and not (
            app_settings.CT_CHAR_ACTIVE_IGNORE_CLONES_MODULE
            or ct_conf.disable_update_clones
        ):
            qs.append(_timestamp_to_epoch("last_update_clones"))

        if app_settings.CT_CHAR_SKILLS_MODULE and not (
            app_settings.CT_CHAR_ACTIVE_IGNORE_SKILLS_MODULE
            or ct_conf.disable_update_skills
        ):
            qs.append(_timestamp_to_epoch("last_update_skills"))
            qs.append(_timestamp_to_epoch("last_update_skill_que"))

        if app_settings.CT_CHAR_WALLET_MODULE and not (
            app_settings.CT_CHAR_ACTIVE_IGNORE_WALLET_MODULE
            or ct_conf.disable_update_wallet
        ):
            qs.append(_timestamp_to_epoch("last_update_wallet"))
            qs.append(_timestamp_to_epoch("last_update_orders"))

        if app_settings.CT_CHAR_NOTIFICATIONS_MODULE and not (
            app_settings.CT_CHAR_ACTIVE_IGNORE_NOTIFICATIONS_MODULE
            or ct_conf.disable_update_notif
        ):
            qs.append(_timestamp_to_epoch("last_update_notif"))

        if app_settings.CT_CHAR_ROLES_MODULE and not (
            app_settings.CT_CHAR_ACTIVE_IGNORE_ROLES_MODULE
            or ct_conf.disable_update_roles
        ):
            qs.append(_timestamp_to_epoch("last_update_roles"))

        if app_settings.CT_CHAR_MAIL_MODULE and not (
            app_settings.CT_CHAR_ACTIVE_IGNORE_MAIL_MODULE
            or ct_conf.disable_update_mails
        ):
            qs.append(_timestamp_to_epoch("last_update_mails"))

        if app_settings.CT_CHAR_LOYALTYPOINTS_MODULE and not (
            app_settings.CT_CHAR_ACTIVE_IGNORE_LOYALTYPOINTS_MODULE
            or ct_conf.disable_update_loyaltypoints
        ):
            qs.append(_timestamp_to_epoch("last_update_loyaltypoints"))

        if app_settings.CT_CHAR_MINING_MODULE and not (
            app_settings.CT_CHAR_ACTIVE_IGNORE_MINING_MODULE
            or ct_conf.disable_update_mining
        ):
            qs.append(_timestamp_to_epoch("last_update_mining"))

        if not qs:
            return cls.objects.none()

        tot = len(qs)
        qout = qs.pop()
        for q in qs:
            qout = qout + q

        return (
            cls.objects.annotate(
                avg_date=_epoch_to_datetime(qout / tot),
            )
            .filter(
                character__character_ownership__isnull=False,
                avg_date__gte=time_ref,
            )
            .order_by("avg_date")
        )

    CharacterAudit.get_oldest_qs = get_oldest_qs
    logger.debug("corptools_postgres_compat: patched CharacterAudit.get_oldest_qs")
