"""Celery tasks for Industrial PI sync."""

from __future__ import annotations

import logging

from celery import shared_task
from django.contrib.auth import get_user_model

logger = logging.getLogger(__name__)
User = get_user_model()


@shared_task(name="emu_pi.sync_all_users")
def sync_all_users() -> dict:
    """Poll PI colonies for every user who can actually be synced, plus
    anyone with alert prefs enabled.

    Real bug fixed here (2026-09-14, "PI not working" report): this used to
    build its worklist from users who *already* had a `PiAlertPref` row or
    *already* had `PiPlanetState` rows — a chicken-and-egg gap for anyone
    who'd never been synced before. Nothing else ever creates that first
    row (the EVE-Penguin bridge, `penguin_bridge/pi.py`, only *reads*
    `PiPlanetState`), so a brand-new linked account could never get its
    first sync from this daily task at all — it would sit at zero rows
    forever unless the user happened to hit the client's manual "Force
    update" button (which calls `sync_user_task` directly, by user id, and
    was never affected by this). Now built from every user with a live
    `esi-planets.manage_planets.v1` token — the actual population this
    task exists to cover.
    """
    from esi.models import Token

    from emu_pi.models import PiAlertPref, PiPlanetState
    from emu_pi.services.sync import PI_SCOPE, sync_user

    user_ids = set(
        Token.objects.filter(scopes__name=PI_SCOPE)
        .exclude(user_id__isnull=True)
        .values_list("user_id", flat=True)
    )
    user_ids.update(
        PiAlertPref.objects.filter(enabled=True).values_list("user_id", flat=True)
    )
    user_ids.update(
        PiPlanetState.objects.filter(archived=False)
        .values_list("user_id", flat=True)
        .distinct()[:500]
    )
    synced = 0
    errors = 0
    for uid in sorted(user_ids):
        user = User.objects.filter(pk=uid).first()
        if not user:
            continue
        try:
            result = sync_user(user, run_alerts=True)
            if result.get("ok"):
                synced += 1
            else:
                errors += 1
        except Exception:
            logger.exception("emu_pi.sync_all_users failed for user %s", uid)
            errors += 1
    return {"synced": synced, "errors": errors, "users": len(user_ids)}


@shared_task(name="emu_pi.sync_user")
def sync_user_task(user_id: int, character_id: int | None = None) -> dict:
    from emu_pi.services.sync import sync_user

    user = User.objects.filter(pk=user_id).first()
    if not user:
        return {"ok": False, "error": "user_not_found"}
    return sync_user(user, character_id=character_id, run_alerts=True)
