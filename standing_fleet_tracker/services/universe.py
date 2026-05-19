"""Resolve EVE type and system names via eveuniverse."""

from __future__ import annotations

from django.apps import apps


def type_name(type_id: int | None) -> str:
    if not type_id:
        return ""
    if not apps.is_installed("eveuniverse"):
        return str(type_id)
    from eveuniverse.models import EveType

    row = EveType.objects.filter(id=type_id).first()
    return row.name if row else str(type_id)


def region_name_for_system(system_id: int | None) -> str:
    if not system_id:
        return ""
    if not apps.is_installed("eveuniverse"):
        return ""
    from eveuniverse.models import EveSolarSystem

    system = EveSolarSystem.objects.filter(id=system_id).select_related("constellation__region").first()
    if not system or not system.constellation_id:
        return ""
    region = getattr(system.constellation, "region", None)
    return region.name if region else ""


def ship_group_name(type_id: int | None) -> str:
    if not type_id:
        return ""
    if not apps.is_installed("eveuniverse"):
        return ""
    from eveuniverse.models import EveType

    row = EveType.objects.filter(id=type_id).select_related("group").first()
    if not row or not row.group_id:
        return type_name(type_id)
    return row.group.name


def solar_system_name(system_id: int | None) -> str:
    if not system_id:
        return ""
    if not apps.is_installed("eveuniverse"):
        return str(system_id)
    from eveuniverse.models import EveSolarSystem

    row = EveSolarSystem.objects.filter(id=system_id).first()
    return row.name if row else str(system_id)
