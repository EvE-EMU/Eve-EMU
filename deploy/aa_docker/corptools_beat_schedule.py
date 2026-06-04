"""Ensure CorpTools Celery Beat tasks run every N minutes (default 30, not hourly)."""

from __future__ import annotations

import logging
import os

from django.apps import apps
from django.db import ProgrammingError

logger = logging.getLogger(__name__)

CHARACTER_TASK = "corptools.tasks.update_subset_of_characters"
CORP_TASK = "corptools.tasks.update_all_corps"
CHARACTER_TASK_NAME = "Character Audit Rolling Update"
CORP_TASK_NAME = "Corporation Audit Update"


def _env_int(name: str, default: int) -> int:
    raw = os.environ.get(name, "").strip()
    if not raw:
        return default
    try:
        return max(1, min(1440, int(raw)))
    except ValueError:
        return default


def _beat_auto_enabled() -> bool:
    return os.environ.get("AA_CORPTOOLS_BEAT_AUTO", "1").strip().lower() in (
        "1",
        "true",
        "yes",
        "on",
    )


def _interval_schedule(every_minutes: int):
    from django_celery_beat.models import IntervalSchedule

    return IntervalSchedule.objects.get_or_create(
        every=every_minutes,
        period=IntervalSchedule.MINUTES,
    )[0]


def _apply_interval_task(
    *,
    task: str,
    name: str,
    every_minutes: int,
) -> bool:
    from django_celery_beat.models import PeriodicTask

    interval = _interval_schedule(every_minutes)
    PeriodicTask.objects.update_or_create(
        task=task,
        defaults={
            "name": name,
            "enabled": True,
            "interval": interval,
            "crontab": None,
            "solar": None,
            "clocked": None,
        },
    )
    return True


def apply_corptools_beat_schedule() -> None:
    """Point CorpTools rolling character + corp audits at interval schedules."""
    if not _beat_auto_enabled():
        return
    if not apps.is_installed("corptools"):
        return
    try:
        char_mins = _env_int("AA_CORPTOOLS_CHARACTER_UPDATE_MINUTES", 30)
        corp_mins = _env_int("AA_CORPTOOLS_CORP_UPDATE_MINUTES", 30)
        _apply_interval_task(
            task=CHARACTER_TASK,
            name=CHARACTER_TASK_NAME,
            every_minutes=char_mins,
        )
        _apply_interval_task(
            task=CORP_TASK,
            name=CORP_TASK_NAME,
            every_minutes=corp_mins,
        )
        logger.info(
            "corptools_beat_schedule: character every %sm, corporation every %sm",
            char_mins,
            corp_mins,
        )
    except ProgrammingError:
        logger.debug("corptools_beat_schedule: django_celery_beat not migrated yet")
    except Exception:
        logger.exception("corptools_beat_schedule: failed to apply beat schedule")
