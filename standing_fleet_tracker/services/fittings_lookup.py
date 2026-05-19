"""Reference fits from the AA fittings app (doctrine fits, not live ESI fittings)."""

from __future__ import annotations

from django.apps import apps


def fitting_for_ship_type(ship_type_id: int):
    if not apps.is_installed("fittings"):
        return None
    from fittings.models import Fitting

    return (
        Fitting.objects.filter(ship_type_type_id=ship_type_id)
        .select_related("ship_type")
        .order_by("-last_updated")
        .first()
    )


def doctrine_fitting_payload(ship_type_id: int) -> dict:
    from standing_fleet_tracker.services.universe import type_name

    fitting = fitting_for_ship_type(ship_type_id)
    if not fitting:
        return {
            "ship_type_id": ship_type_id,
            "ship_type_name": type_name(ship_type_id),
            "has_fitting": False,
            "fitting_name": "",
            "eft": "",
            "everef_url": f"https://everef.com/types/{ship_type_id}",
            "source": "none",
            "message": "",
            "visual_html": "",
            "fitting_id": None,
        }
    return {
        "ship_type_id": ship_type_id,
        "ship_type_name": type_name(ship_type_id),
        "has_fitting": True,
        "fitting_name": fitting.name,
        "eft": fitting.eft,
        "everef_url": f"https://everef.com/types/{ship_type_id}",
        "source": "doctrine",
        "message": "",
        "visual_html": "",
        "fitting_id": fitting.pk,
    }


def fitting_payload(ship_type_id: int) -> dict:
    return doctrine_fitting_payload(ship_type_id)
