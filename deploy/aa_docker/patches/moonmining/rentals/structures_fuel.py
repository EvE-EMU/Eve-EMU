"""Sync lease fuel % from aa-structures (or CorpTools fuel expiry fallback)."""

from __future__ import annotations

import logging
from typing import TYPE_CHECKING

from django.apps import apps

if TYPE_CHECKING:
    from moonmining.models import Moon

    from .models import MoonLease

logger = logging.getLogger(__name__)


def _reference_hours(settings) -> float:
    hours = float(getattr(settings, "fuel_reference_hours", 720) or 720)
    return max(hours, 1.0)


def fuel_percent_from_hours(hours_remaining: float | None, *, reference_hours: float) -> int | None:
    if hours_remaining is None:
        return None
    return max(0, min(100, int(round((hours_remaining / reference_hours) * 100))))


def find_structure_for_moon(moon: Moon):
    """Match aa-structures Structure by moon id or moonmining refinery pk."""
    if not apps.is_installed("structures"):
        return None

    from structures.models import Structure

    structure = (
        Structure.objects.filter(eve_moon_id=moon.pk)
        .order_by("-last_updated_at")
        .first()
    )
    if structure:
        return structure

    refinery = getattr(moon, "refinery", None)
    if refinery is not None:
        return Structure.objects.filter(pk=refinery.pk).first()
    return None


def fuel_percent_for_moon(moon: Moon, *, reference_hours: float) -> int | None:
    structure = find_structure_for_moon(moon)
    if structure is not None:
        try:
            hours = structure.hours_fuel_expires
        except Exception:
            hours = None
        percent = fuel_percent_from_hours(hours, reference_hours=reference_hours)
        if percent is not None:
            return percent

    if apps.is_installed("corptools"):
        percent = _fuel_percent_from_corptools(moon, reference_hours=reference_hours)
        if percent is not None:
            return percent

    return None


def _fuel_percent_from_corptools(moon: Moon, *, reference_hours: float) -> int | None:
    try:
        from corptools.models import Structure as CtStructure
        from django.utils import timezone
    except ImportError:
        return None

    refinery = getattr(moon, "refinery", None)
    qs = CtStructure.objects.filter(fuel_expires__isnull=False)
    if refinery is not None:
        qs = qs.filter(structure_id=refinery.id)
    else:
        return None

    ct = qs.order_by("fuel_expires").first()
    if not ct or not ct.fuel_expires:
        return None

    remaining = (ct.fuel_expires - timezone.now()).total_seconds() / 3600.0
    return fuel_percent_from_hours(remaining, reference_hours=reference_hours)


def sync_lease_fuel_from_structures(lease: MoonLease, *, save: bool = True) -> bool:
    from .models import RentalModuleSettings

    settings = RentalModuleSettings.load()
    percent = fuel_percent_for_moon(
        lease.moon,
        reference_hours=_reference_hours(settings),
    )
    if percent is None:
        return False
    lease.fuel_percent = percent
    if save:
        lease.save(update_fields=["fuel_percent", "updated_at"])
    return True


def sync_all_lease_fuel_from_structures() -> dict[str, int]:
    from .models import MoonLease

    updated = 0
    skipped = 0
    for lease in MoonLease.objects.filter(
        status__in=(MoonLease.STATUS_ACTIVE, MoonLease.STATUS_GRACE)
    ).select_related("moon"):
        if sync_lease_fuel_from_structures(lease):
            updated += 1
        else:
            skipped += 1
    return {"updated": updated, "skipped": skipped}
