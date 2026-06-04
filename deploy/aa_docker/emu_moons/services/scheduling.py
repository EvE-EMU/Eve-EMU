"""Extraction scheduling assistant for /moonmining/extractions."""

from __future__ import annotations

import re
from datetime import datetime, timedelta
from typing import Any

from django.utils import timezone

from emu_moons.models import EmuMoonsSettings, StructureClass, StructureTaxProfile

_SYSTEM_FROM_NAME = re.compile(r"^([A-Z0-9-]+)\s")
_REFINERY_SELECT = (
    "moon",
    "owner",
    "moon__eve_moon__eve_planet__eve_solar_system",
    "moon__eve_moon__eve_planet__eve_solar_system__eve_constellation",
    "moon__eve_moon__eve_planet__eve_solar_system__eve_constellation__eve_region",
)


def _system_name(refinery) -> str:
    name = str(refinery.name or refinery)
    m = _SYSTEM_FROM_NAME.match(name)
    if m:
        return m.group(1)
    moon = getattr(refinery, "moon", None)
    if moon:
        m2 = _SYSTEM_FROM_NAME.match(str(moon))
        if m2:
            return m2.group(1)
    try:
        solar = moon.eve_moon.eve_planet.eve_solar_system
        return solar.name if solar else ""
    except Exception:
        return ""


def _structure_class(refinery_id: int, refinery_name: str = "") -> str:
    prof = StructureTaxProfile.objects.filter(moonmining_refinery_id=refinery_id).first()
    if prof:
        return prof.structure_class
    upper = (refinery_name or "").upper()
    if "NATIONALISED" in upper or "NATIONALIZED" in upper:
        return StructureClass.NATIONALIZED
    if "PRIVATE" in upper:
        return StructureClass.PRIVATE
    return StructureClass.PUBLIC


def _moon_meta(refinery) -> dict[str, str]:
    moon = getattr(refinery, "moon", None)
    moon_name = str(moon) if moon else str(refinery.name or "")
    region_name = constellation_name = corporation_name = alliance_name = ""
    rarity_class = ""
    if moon:
        try:
            rarity_class = moon.get_rarity_class_display()
        except Exception:
            pass
    try:
        owner = refinery.owner
        if owner:
            corporation_name = owner.name or ""
            alliance_name = getattr(owner, "alliance_name", "") or ""
    except Exception:
        pass
    try:
        solar = moon.eve_moon.eve_planet.eve_solar_system
        constellation_name = solar.eve_constellation.name
        region_name = solar.eve_constellation.eve_region.name
    except Exception:
        pass
    return {
        "moon_name": moon_name,
        "region_name": region_name,
        "constellation_name": constellation_name,
        "corporation_name": corporation_name,
        "alliance_name": alliance_name,
        "rarity_class": rarity_class,
    }


def suggest_next_extraction(
    *,
    structure_class: str,
    system_name: str,
    existing_pops: list[datetime],
    blocked_dates: set,
) -> datetime | None:
    """Nationalized: Friday 18:00 UTC. Others: >=30d, avoid blocked calendar days."""
    cfg = EmuMoonsSettings.load()
    now = timezone.now()
    candidate = now + timedelta(days=30)
    if structure_class == StructureClass.NATIONALIZED:
        while candidate.weekday() != cfg.nationalized_extract_dow or candidate <= now:
            candidate += timedelta(days=1)
        candidate = candidate.replace(
            hour=cfg.nationalized_extract_hour,
            minute=0,
            second=0,
            microsecond=0,
        )
        if timezone.is_naive(candidate):
            candidate = timezone.make_aware(candidate)
    else:
        candidate = candidate.replace(hour=18, minute=0, second=0, microsecond=0)
        if timezone.is_naive(candidate):
            candidate = timezone.make_aware(candidate)

    used = {p.date() for p in existing_pops if p} | blocked_dates
    for _ in range(400):
        if candidate.date() not in used:
            if system_name and structure_class in (
                StructureClass.PUBLIC,
                StructureClass.PRIVATE,
            ):
                prev = candidate - timedelta(days=1)
                if prev.date() in blocked_dates:
                    candidate += timedelta(days=1)
                    continue
            return candidate
        candidate += timedelta(days=1)
    return None


def scheduling_rows_for_moonmining() -> list[dict[str, Any]]:
    try:
        from moonmining.models import Extraction, Refinery
    except ImportError:
        return []

    upcoming_by_system: dict[str, list[datetime]] = {}
    for ext in Extraction.objects.filter(
        started_at__gte=timezone.now() - timedelta(days=7)
    ).select_related("refinery"):
        sys = _system_name(ext.refinery) if ext.refinery_id else ""
        when = ext.chunk_arrival_at or ext.started_at
        if sys and when:
            upcoming_by_system.setdefault(sys, []).append(when)

    blocked: set = set()
    for pops in upcoming_by_system.values():
        for p in pops:
            blocked.add(p.date())

    rows: list[dict[str, Any]] = []
    for ref in Refinery.objects.select_related(*_REFINERY_SELECT).order_by("name"):
        ref_name = ref.name or ""
        sclass = _structure_class(ref.pk, ref_name)
        system = _system_name(ref)
        meta = _moon_meta(ref)
        recent = list(
            Extraction.objects.filter(refinery=ref)
            .exclude(started_at__isnull=True)
            .order_by("-started_at")[:10]
        )
        pop_times = [
            ext.chunk_arrival_at or ext.started_at
            for ext in recent
            if ext.chunk_arrival_at or ext.started_at
        ]
        last_extraction_id = recent[0].pk if recent else None
        suggested = suggest_next_extraction(
            structure_class=sclass,
            system_name=system,
            existing_pops=pop_times,
            blocked_dates=blocked,
        )
        if suggested:
            blocked.add(suggested.date())
        rows.append(
            {
                "refinery": ref,
                "refinery_id": ref.pk,
                "moon_id": ref.moon_id,
                "structure_name": ref_name or meta["moon_name"],
                "moon_label": meta["moon_name"],
                "system_name": system,
                "structure_class": sclass,
                "structure_class_display": dict(StructureClass.choices).get(
                    sclass, sclass
                ),
                "suggested_at": suggested,
                "last_pop": pop_times[0] if pop_times else None,
                "last_extraction_id": last_extraction_id,
                **meta,
            }
        )
    rows.sort(key=lambda r: (r["system_name"], r["structure_name"]))
    return rows
