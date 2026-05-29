"""Sync Discord nickname when Django group membership changes (Secure Groups, admin, etc.)."""

from __future__ import annotations

import logging
import os
from functools import partial

from django.apps import apps
from django.db import transaction
from django.db.models.signals import m2m_changed

logger = logging.getLogger(__name__)

_registered = False
_permissions_applied = False


def ensure_discord_service_state_permissions() -> None:
    """Grant ``discord.access_discord`` on Member/Blue states so /services/ shows Discord."""
    global _permissions_applied
    if _permissions_applied:
        return
    if os.environ.get("AA_DISCORD_GRANT_STATE_ACCESS", "1").strip().lower() in (
        "0",
        "false",
        "no",
        "off",
    ):
        return
    if not apps.is_installed("allianceauth.services.modules.discord"):
        return
    from django.contrib.auth.models import Permission
    from django.db.utils import OperationalError, ProgrammingError

    from allianceauth.authentication.models import State

    try:
        perm = Permission.objects.get(
            content_type__app_label="discord",
            codename="access_discord",
        )
    except (Permission.DoesNotExist, ProgrammingError, OperationalError):
        return

    raw = os.environ.get("AA_DISCORD_GRANT_STATE_ACCESS_NAMES", "Member,Blue")
    state_names = [n.strip() for n in raw.split(",") if n.strip()]
    for name in state_names:
        try:
            state = State.objects.get(name=name)
        except State.DoesNotExist:
            continue
        if not state.permissions.filter(pk=perm.pk).exists():
            state.permissions.add(perm)
            logger.info("Granted discord.access_discord on state %s", name)
    _permissions_applied = True


def register_discord_group_nickname_sync() -> None:
    global _registered
    if _registered:
        return
    if not apps.is_installed("allianceauth.services.modules.discord"):
        return
    from django.contrib.auth.models import User

    m2m_changed.connect(
        discord_sync_nickname_on_group_change,
        sender=User.groups.through,
        weak=False,
    )
    _registered = True
    logger.info("Discord nickname sync on group membership change is enabled")


def discord_sync_nickname_on_group_change(
    sender, instance, action, pk_set=None, **kwargs
):
    from django.contrib.auth.models import User

    if action not in ("post_add", "post_remove", "post_clear"):
        return
    if not isinstance(instance, User) or not instance.pk:
        return
    if not apps.is_installed("allianceauth.services.modules.discord"):
        return

    from allianceauth.services.modules.discord.app_settings import DISCORD_SYNC_NAMES
    from allianceauth.services.modules.discord.models import DiscordUser

    if not DISCORD_SYNC_NAMES:
        return
    if not DiscordUser.objects.user_has_account(instance):
        return

    transaction.on_commit(partial(_queue_discord_nickname_sync, instance.pk))


def _queue_discord_nickname_sync(user_pk: int) -> None:
    from django.contrib.auth.models import User

    from allianceauth.services.hooks import ServicesHook

    user = User.objects.get(pk=user_pk)
    for svc in ServicesHook.get_services():
        if svc.name != "discord":
            continue
        try:
            svc.sync_nickname(user)
        except Exception:
            logger.exception("Discord nickname sync failed for user pk=%s", user_pk)
