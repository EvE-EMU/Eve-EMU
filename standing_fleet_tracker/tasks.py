from celery import shared_task
from allianceauth.services.tasks import QueueOnce

from standing_fleet_tracker.services.polling import poll_all_characters
from standing_fleet_tracker.services.scoring import (
    accrue_kill_bonuses,
    accrue_sov_roam_penalties,
    accrue_standing_hours,
    rebuild_character_scores,
)
from standing_fleet_tracker.services.fit_snapshots import purge_old_snapshots
from standing_fleet_tracker.services.monthly_kpi import compute_all_characters_for_month
from standing_fleet_tracker.services.sov import refresh_sov_cache, sov_cache_stale


@shared_task(base=QueueOnce, once={"graceful": True, "timeout": 600})
def sft_poll_all_characters():
    return poll_all_characters()


@shared_task
def sft_accrue_points():
    standing = accrue_standing_hours()
    kills = accrue_kill_bonuses()
    penalties = accrue_sov_roam_penalties()
    return {"standing": standing, "kills": kills, "penalties": penalties}


@shared_task
def sft_refresh_sov_cache():
    if sov_cache_stale():
        return {"systems": refresh_sov_cache()}
    return {"systems": "skipped"}


@shared_task
def sft_rebuild_scores():
    return {"characters": rebuild_character_scores()}


@shared_task
def sft_purge_fit_snapshots():
    return {"deleted": purge_old_snapshots()}


@shared_task
def sft_compute_monthly_kpis():
    from django.utils import timezone

    now = timezone.now()
    year, month = now.year, now.month
    if month == 1:
        year, month = year - 1, 12
    else:
        month -= 1
    return {"year": year, "month": month, "characters": compute_all_characters_for_month(year, month)}
