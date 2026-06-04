"""Moon extraction calendar events for /moonmining/calendar."""

from __future__ import annotations

from datetime import datetime, timedelta
from typing import Any

from django.contrib.auth.models import User
from django.utils import timezone

from emu_moons.models import StructureClass, StructureTaxProfile
from emu_moons.services.scheduling import (
    _moon_meta,
    _structure_class,
    _system_name,
    scheduling_rows_for_moonmining,
)

_CLASS_COLORS = {
    StructureClass.PUBLIC: "#0d6efd",
    StructureClass.NATIONALIZED: "#fd7e14",
    StructureClass.PRIVATE: "#6c757d",
}
_SUGGESTED_COLORS = {
    StructureClass.PUBLIC: "#6ea8fe",
    StructureClass.NATIONALIZED: "#ffc107",
    StructureClass.PRIVATE: "#adb5bd",
}


def user_owns_private_refinery_ids(user: User) -> set[int]:
    return set(
        StructureTaxProfile.objects.filter(private_owner=user)
        .exclude(moonmining_refinery_id__isnull=True)
        .values_list("moonmining_refinery_id", flat=True)
    )


def user_can_access_calendar(user: User) -> bool:
    if not user.is_authenticated:
        return False
    if user.has_perm("moonmining.extractions_access") and user.has_perm(
        "moonmining.basic_access"
    ):
        return True
    return bool(user_owns_private_refinery_ids(user))


def user_sees_all_calendar_events(user: User) -> bool:
    return user.has_perm("emu_moons.emu_moons_admin") or user.has_perm(
        "emu_moons.emu_moons_view_alliance"
    )


def user_can_see_calendar_event(
    user: User,
    *,
    structure_class: str,
    refinery_id: int | None,
) -> bool:
    if user_sees_all_calendar_events(user):
        return True
    owned = user_owns_private_refinery_ids(user)
    if structure_class == StructureClass.PRIVATE:
        return refinery_id in owned if refinery_id else False
    if user.has_perm("moonmining.extractions_access"):
        return structure_class in (
            StructureClass.PUBLIC,
            StructureClass.NATIONALIZED,
        )
    return False


def _event_base(
    *,
    event_id: str,
    title: str,
    start: datetime,
    structure_class: str,
    structure_class_display: str,
    location: str,
    system_name: str,
    moon_name: str,
    refinery_id: int | None,
    moon_id: int | None,
    event_kind: str,
    extraction_id: int | None = None,
    status: str = "",
) -> dict[str, Any]:
    sc = getattr(structure_class, "value", structure_class)
    colors = _SUGGESTED_COLORS if event_kind == "suggested" else _CLASS_COLORS
    color = colors.get(sc, "#0d6efd")
    return {
        "id": event_id,
        "title": title,
        "start": timezone.localtime(start).isoformat(),
        "backgroundColor": color,
        "borderColor": color,
        "extendedProps": {
            "structure_class": sc,
            "structure_class_display": structure_class_display,
            "location": location,
            "system_name": system_name,
            "moon_name": moon_name,
            "refinery_id": refinery_id,
            "moon_id": moon_id,
            "event_kind": event_kind,
            "extraction_id": extraction_id,
            "status": status,
        },
    }


def _location_label(refinery, meta: dict[str, str]) -> tuple[str, str, str]:
    moon_name = meta.get("moon_name") or str(refinery.name or "")
    system_name = meta.get("system_name") or _system_name(refinery)
    region = meta.get("region_name") or ""
    location = f"{moon_name} — {system_name}"
    if region:
        location = f"{location} ({region})"
    return moon_name, system_name, location


def calendar_events_for_user(
    user: User,
    *,
    range_start: datetime | None = None,
    range_end: datetime | None = None,
    include_suggested: bool = True,
) -> list[dict[str, Any]]:
    if not user_can_access_calendar(user):
        return []

    now = timezone.now()
    if range_start is None:
        range_start = now - timedelta(days=30)
    if range_end is None:
        range_end = now + timedelta(days=120)
    if timezone.is_naive(range_start):
        range_start = timezone.make_aware(range_start)
    if timezone.is_naive(range_end):
        range_end = timezone.make_aware(range_end)

    events: list[dict[str, Any]] = []
    class_labels = dict(StructureClass.choices)

    try:
        from moonmining.models import Extraction
    except ImportError:
        Extraction = None  # type: ignore

    if Extraction is not None:
        qs = (
            Extraction.objects.exclude(refinery__moon__isnull=True)
            .exclude(status=Extraction.Status.CANCELED)
            .select_related(
                "refinery",
                "refinery__moon",
                "refinery__moon__eve_moon__eve_planet__eve_solar_system",
                "refinery__moon__eve_moon__eve_planet__eve_solar_system__eve_constellation",
                "refinery__moon__eve_moon__eve_planet__eve_solar_system__eve_constellation__eve_region",
            )
        )
        for extraction in qs:
            when = extraction.chunk_arrival_at or extraction.auto_fracture_at
            if not when or when < range_start or when > range_end:
                continue
            refinery = extraction.refinery
            refinery_id = refinery.pk if refinery else None
            sclass = _structure_class(refinery_id or 0, str(refinery.name or ""))
            if not user_can_see_calendar_event(
                user, structure_class=sclass, refinery_id=refinery_id
            ):
                continue
            meta = _moon_meta(refinery) if refinery else {}
            moon_name, system_name, location = _location_label(refinery, meta)
            title = str(refinery.name or moon_name)
            status = ""
            try:
                status = extraction.get_status_display()
            except Exception:
                status = str(getattr(extraction, "status", "") or "")
            events.append(
                _event_base(
                    event_id=f"ext-{extraction.pk}",
                    title=title,
                    start=when,
                    structure_class=sclass,
                    structure_class_display=class_labels.get(sclass, sclass),
                    location=location,
                    system_name=system_name,
                    moon_name=moon_name,
                    refinery_id=refinery_id,
                    moon_id=getattr(refinery, "moon_id", None),
                    event_kind="scheduled",
                    extraction_id=extraction.pk,
                    status=status,
                )
            )

    if include_suggested and (
        user.has_perm("moonmining.extractions_access")
        or user_sees_all_calendar_events(user)
        or user_owns_private_refinery_ids(user)
    ):
        for row in scheduling_rows_for_moonmining():
            when = row.get("suggested_at")
            if not when or when < range_start or when > range_end:
                continue
            refinery_id = row.get("refinery_id")
            sclass = row["structure_class"]
            if not user_can_see_calendar_event(
                user, structure_class=sclass, refinery_id=refinery_id
            ):
                continue
            refinery = row["refinery"]
            meta = {k: row.get(k, "") for k in (
                "moon_name",
                "region_name",
                "system_name",
            )}
            moon_name, system_name, location = _location_label(refinery, meta)
            title = row.get("structure_name") or moon_name
            events.append(
                _event_base(
                    event_id=f"sug-{refinery_id}",
                    title=f"{title} ({class_labels.get(sclass, sclass)})",
                    start=when,
                    structure_class=sclass,
                    structure_class_display=row.get("structure_class_display", sclass),
                    location=location,
                    system_name=system_name,
                    moon_name=moon_name,
                    refinery_id=refinery_id,
                    moon_id=row.get("moon_id"),
                    event_kind="suggested",
                )
            )

    events.sort(key=lambda e: e["start"])
    return events
