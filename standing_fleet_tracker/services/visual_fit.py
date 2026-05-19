"""Render AA Fittings visual fitting panel for live ESI or doctrine fits."""

from __future__ import annotations

import logging
from types import SimpleNamespace
from typing import Any

from django.apps import apps
from django.template.loader import render_to_string

logger = logging.getLogger(__name__)


def _fittings_visual_available() -> bool:
    return apps.is_installed("fittings") and apps.is_installed("eve_sde")


def _item_type(type_id: int):
    from eve_sde.models import ItemType

    return ItemType.objects.filter(id=type_id).first()


def _visual_item(type_id: int):
    type_fk = _item_type(type_id)
    if not type_fk:
        return None
    return SimpleNamespace(type_id=type_id, type_fk=type_fk)


def _fitting_dict_from_flagged_rows(rows: list[dict[str, Any]]) -> dict[str, Any]:
    """Build fittings template `fitting` dict from ESI assets or FittingItem rows."""
    fitting: dict[str, Any] = {
        "Cargo": [],
        "FighterBay": [],
        "DroneBay": [],
    }
    for row in rows:
        flag = str(row.get("flag") or row.get("location_flag") or "")
        type_id = int(row["type_id"])
        item = _visual_item(type_id)
        if not item:
            continue
        if flag in ("Cargo", "FighterBay", "DroneBay"):
            fitting[flag].append(item)
        elif flag:
            fitting[flag] = item
    return fitting


def build_slots_for_ship_type(ship_type_id: int) -> dict[str, int]:
    """Slot grid counts from ship dogma (matches fittings view layout)."""
    from eve_sde.models import ItemType, TypeDogma

    ship = ItemType.objects.filter(id=ship_type_id).first()
    if not ship:
        return {"low": 0, "med": 0, "high": 0, "rig": 0}

    attributes = (12, 13, 14, 1137, 1367, 2056)
    t3c = TypeDogma.objects.filter(dogma_attribute_id=1367, item_type_id=ship.id).exists()
    slots: dict[str, int] = {"low": 0, "med": 0, "high": 0}

    for attribute in TypeDogma.objects.filter(dogma_attribute_id__in=attributes, item_type=ship):
        if attribute.dogma_attribute_id == 1367 and t3c:
            slots["sub"] = 4
        elif attribute.dogma_attribute_id == 12:
            slots["low"] += int(attribute.value)
        elif attribute.dogma_attribute_id == 13:
            slots["med"] += int(attribute.value)
        elif attribute.dogma_attribute_id == 14:
            slots["high"] += int(attribute.value)
        elif attribute.dogma_attribute_id == 1137:
            slots["rig"] = int(attribute.value)

    return slots


def _fit_stub(*, name: str, ship_type_id: int, ship_type) -> SimpleNamespace:
    return SimpleNamespace(
        name=name,
        ship_type_type_id=ship_type_id,
        ship_type=ship_type,
        description="",
    )


def render_visual_fitting_html(
    request,
    *,
    ship_type_id: int,
    fit_name: str,
    flagged_rows: list[dict[str, Any]] | None = None,
    fitting_id: int | None = None,
) -> str:
    """
    Return HTML for the fittings app slot panel (hi/med/low/rig + ship render).
    Uses doctrine Fitting from DB when fitting_id is set; otherwise flagged module rows.
    """
    if not _fittings_visual_available():
        return ""

    try:
        if fitting_id:
            return _render_from_fitting_id(request, fitting_id)

        if not flagged_rows:
            return ""

        ship_type = _item_type(ship_type_id)
        if not ship_type:
            return ""

        fitting = _fitting_dict_from_flagged_rows(flagged_rows)
        slots = build_slots_for_ship_type(ship_type_id)
        fit = _fit_stub(name=fit_name, ship_type_id=ship_type_id, ship_type=ship_type)

        panel = render_to_string(
            "fittings/partials/view-fit/fitting.html",
            {
                "fit": fit,
                "fitting": fitting,
                "slots": slots,
                "cats": [],
            },
            request=request,
        )
        return '<div class="aa-fittings sft-fit-visual-wrap">' + panel + '</div>'
    except Exception as exc:
        logger.warning("SFT visual fit render failed: %s", exc, exc_info=True)
        return ""


def _render_from_fitting_id(request, fitting_id: int) -> str:
    from fittings.models import Fitting, FittingItem
    from fittings.views import _build_slots

    fit = Fitting.objects.select_related("ship_type").get(pk=fitting_id)
    items = FittingItem.objects.filter(fit=fit).select_related("type_fk")

    fitting: dict[str, Any] = {
        "Cargo": [],
        "FighterBay": [],
        "DroneBay": [],
    }
    for item in items:
        if item.flag == "Cargo":
            fitting["Cargo"].append(item)
        elif item.flag == "DroneBay":
            fitting["DroneBay"].append(item)
        elif item.flag == "FighterBay":
            fitting["FighterBay"].append(item)
        else:
            fitting[item.flag] = item

    panel = render_to_string(
        "fittings/partials/view-fit/fitting.html",
        {
            "fit": fit,
            "fitting": fitting,
            "slots": _build_slots(fit),
            "cats": [],
        },
        request=request,
    )
    return f'<div class="aa-fittings sft-fit-visual-wrap">{panel}</div>'
