"""Celery tasks: compliance refresh and weekly Discord report."""

from __future__ import annotations

import os

from celery import shared_task

from allianceauth.services.hooks import get_extension_logger

logger = get_extension_logger(__name__)


def _task_enabled() -> bool:
    return os.environ.get("AA_MOON_RENTALS_CELERY", "1").strip().lower() in (
        "1",
        "true",
        "yes",
        "on",
    )


@shared_task
def moon_rentals_refresh_compliance() -> dict:
    """Refresh compliance for pops in or recently past their tracking window."""
    if not _task_enabled():
        return {"skipped": True, "reason": "AA_MOON_RENTALS_CELERY disabled"}
    from .reporting import refresh_pops_for_report

    count = refresh_pops_for_report(lookback_days=21)
    logger.info("moon_rentals: refreshed compliance for %s pop(s)", count)
    return {"refreshed": count}


@shared_task
def moon_rentals_weekly_discord_report() -> dict:
    """Weekly Discord summary of moon pop buyback compliance."""
    if not _task_enabled():
        return {"skipped": True, "reason": "AA_MOON_RENTALS_CELERY disabled"}
    from .discord import discord_enabled, send_weekly_report
    from .reporting import build_weekly_report

    if not discord_enabled():
        return {"skipped": True, "reason": "Discord webhook not configured"}

    data = build_weekly_report(refresh=True)
    ok = send_weekly_report(data)
    return {
        "posted": ok,
        "action_required": len(data.get("action_required") or []),
        "in_progress": len(data.get("in_progress") or []),
        "private_issues": len(data.get("private_issues") or []),
    }
