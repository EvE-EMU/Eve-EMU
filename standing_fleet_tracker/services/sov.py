"""Alliance sov solar system cache."""

from __future__ import annotations

from datetime import timedelta

from django.utils import timezone

from standing_fleet_tracker import app_settings
from standing_fleet_tracker.models import SovSystemCache
from standing_fleet_tracker.services.esi import get_sovereignty_map


def refresh_sov_cache(alliance_id: int | None = None) -> int:
    alliance_id = alliance_id or app_settings.SFT_ALLIANCE_ID
    mapping = get_sovereignty_map()
    if not mapping:
        return 0

    now = timezone.now()
    count = 0
    for system_id, owner_alliance in mapping.items():
        if int(owner_alliance) != int(alliance_id):
            continue
        SovSystemCache.objects.update_or_create(
            alliance_id=alliance_id,
            solar_system_id=int(system_id),
            defaults={"updated_at": now},
        )
        count += 1
    SovSystemCache.objects.filter(alliance_id=alliance_id).exclude(
        updated_at__gte=now - timedelta(seconds=5)
    ).delete()
    return count


def is_system_in_sov(solar_system_id: int, alliance_id: int | None = None) -> bool:
    alliance_id = alliance_id or app_settings.SFT_ALLIANCE_ID
    return SovSystemCache.objects.filter(
        alliance_id=alliance_id,
        solar_system_id=solar_system_id,
    ).exists()


def sov_cache_stale(alliance_id: int | None = None) -> bool:
    alliance_id = alliance_id or app_settings.SFT_ALLIANCE_ID
    row = SovSystemCache.objects.filter(alliance_id=alliance_id).order_by("-updated_at").first()
    if not row:
        return True
    age = timezone.now() - row.updated_at
    return age > timedelta(hours=app_settings.SFT_SOV_CACHE_HOURS)
