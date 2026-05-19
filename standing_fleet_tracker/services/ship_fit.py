"""Build ship fittings from live ESI (ship + assets) with doctrine fallback."""

from __future__ import annotations

import logging
from typing import Any

from standing_fleet_tracker.services import esi as esi_api
from standing_fleet_tracker.services.fittings_lookup import doctrine_fitting_payload
from standing_fleet_tracker.services.scopes import missing_scopes_for_token
from standing_fleet_tracker.services.universe import type_name
from standing_fleet_tracker.services.visual_fit import render_visual_fitting_html

logger = logging.getLogger(__name__)

ASSETS_SCOPE = "esi-assets.read_assets.v1"

# ESI location_flag values for modules fitted to a ship (not cargo/hangar).
_FIT_SLOT_PREFIXES = (
    "HiSlot",
    "MedSlot",
    "LoSlot",
    "RigSlot",
    "SubSystemSlot",
    "ServiceSlot",
    "FighterTube",
    "DroneBay",
)


def _is_fitted_module_flag(flag: str) -> bool:
    return any(flag.startswith(prefix) for prefix in _FIT_SLOT_PREFIXES)


def _slot_sort_key(flag: str) -> tuple[int, int, str]:
    for idx, prefix in enumerate(_FIT_SLOT_PREFIXES):
        if flag.startswith(prefix):
            suffix = flag[len(prefix) :]
            try:
                return (idx, int(suffix), "")
            except ValueError:
                return (idx, 0, suffix)
    return (len(_FIT_SLOT_PREFIXES), 0, flag)


def _module_line(type_id: int, quantity: int) -> str:
    name = type_name(type_id)
    if quantity > 1:
        return f"{name} x{quantity}"
    return name


def build_eft_from_fitted_items(
    ship_type_id: int,
    *,
    ship_name: str = "",
    fitted_items: list[dict[str, Any]],
) -> str:
    """Approximate Pyfa/EFT text from ESI asset rows on the ship."""
    hull = type_name(ship_type_id)
    title = ship_name.strip() or hull
    lines = [f"{hull}, {title}", ""]

    sorted_items = sorted(
        fitted_items,
        key=lambda row: _slot_sort_key(str(row.get("location_flag") or "")),
    )
    for row in sorted_items:
        flag = str(row.get("location_flag") or "")
        if not _is_fitted_module_flag(flag):
            continue
        type_id = int(row["type_id"])
        qty = int(row.get("quantity") or 1)
        lines.append(_module_line(type_id, qty))

    if len(lines) <= 2:
        return ""
    return "\n".join(lines)


def _fitted_items_on_ship(assets: list[dict[str, Any]], ship_item_id: int) -> list[dict[str, Any]]:
    return [
        row
        for row in assets
        if int(row.get("location_id") or 0) == ship_item_id and _is_fitted_module_flag(str(row.get("location_flag") or ""))
    ]


def _attach_visual(
    payload: dict[str, Any],
    request,
    *,
    flagged_rows: list[dict[str, Any]] | None = None,
    fitting_id: int | None = None,
) -> dict[str, Any]:
    if request is None:
        return payload
    payload["visual_html"] = render_visual_fitting_html(
        request,
        ship_type_id=int(payload["ship_type_id"]),
        fit_name=payload.get("fitting_name") or payload.get("ship_type_name") or "Fit",
        flagged_rows=flagged_rows,
        fitting_id=fitting_id or payload.get("fitting_id"),
    )
    return payload


def live_ship_fit_payload(
    character_id: int,
    ship_type_id_hint: int | None = None,
    *,
    request=None,
) -> dict[str, Any]:
    """Resolve fit via GET /characters/{id}/ship/ + assets on ship_item_id."""
    base: dict[str, Any] = {
        "ship_type_id": ship_type_id_hint or 0,
        "ship_type_name": type_name(ship_type_id_hint) if ship_type_id_hint else "",
        "ship_name": "",
        "has_fitting": False,
        "fitting_name": "",
        "eft": "",
        "everef_url": f"https://everef.com/types/{ship_type_id_hint}" if ship_type_id_hint else "",
        "source": "none",
        "message": "",
        "visual_html": "",
        "fitting_id": None,
    }

    token = esi_api.token_for_character(character_id)
    if not token:
        base["message"] = "No ESI token for this character."
        return _merge_doctrine_fallback(base, character_id, ship_type_id_hint, request=request)

    missing = missing_scopes_for_token(token)
    if ASSETS_SCOPE in missing:
        base["message"] = f"Missing {ASSETS_SCOPE} on Charlink — enable assets scope for live fits."
        return _merge_doctrine_fallback(base, character_id, ship_type_id_hint, request=request)

    ship_status, ship = esi_api.get_character_ship(character_id, token)
    if ship_status != 200 or not ship:
        base["message"] = "Could not read current ship from ESI."
        return _merge_doctrine_fallback(base, character_id, ship_type_id_hint, request=request)

    ship_item_id = int(ship["ship_item_id"])
    live_type_id = int(ship["ship_type_id"])
    live_name = str(ship.get("ship_name") or "")
    base["ship_type_id"] = live_type_id
    base["ship_type_name"] = type_name(live_type_id)
    base["ship_name"] = live_name
    base["everef_url"] = f"https://everef.com/types/{live_type_id}"

    if ship_type_id_hint and ship_type_id_hint != live_type_id:
        base["message"] = (
            f"Character is currently in {base['ship_type_name']}, not {type_name(ship_type_id_hint)}. "
            "Showing live fit for the ship they are in now."
        )

    assets = esi_api.get_character_assets(character_id, token)
    if assets is None:
        base["message"] = (base.get("message") or "") + " Could not load character assets from ESI."
        return _merge_doctrine_fallback(
            base, character_id, ship_type_id_hint or live_type_id, request=request
        )

    fitted = _fitted_items_on_ship(assets, ship_item_id)
    eft = build_eft_from_fitted_items(live_type_id, ship_name=live_name, fitted_items=fitted)
    if eft:
        base.update(
            {
                "has_fitting": True,
                "fitting_name": "Live fit (ESI)",
                "eft": eft,
                "source": "esi_live",
            }
        )
        return _attach_visual(base, request, flagged_rows=fitted)

    base["message"] = (base.get("message") or "") + " No fitted modules found on this ship."
    return _merge_doctrine_fallback(base, character_id, live_type_id, request=request)


def _merge_doctrine_fallback(
    base: dict[str, Any],
    character_id: int,
    ship_type_id: int | None,
    *,
    request=None,
) -> dict[str, Any]:
    tid = ship_type_id or base.get("ship_type_id") or 0
    if not tid:
        return base
    doctrine = doctrine_fitting_payload(tid)
    if doctrine.get("has_fitting") and doctrine.get("eft"):
        if not base.get("message"):
            base["message"] = doctrine.get("message", "")
        base.update(
            {
                "has_fitting": True,
                "fitting_name": doctrine.get("fitting_name") or "Doctrine fit",
                "eft": doctrine["eft"],
                "source": "doctrine",
                "ship_type_id": doctrine["ship_type_id"],
                "ship_type_name": doctrine["ship_type_name"],
                "everef_url": doctrine["everef_url"],
                "fitting_id": doctrine.get("fitting_id"),
            }
        )
        return _attach_visual(
            base,
            request,
            fitting_id=doctrine.get("fitting_id"),
        )
    elif not base.get("message"):
        base["message"] = doctrine.get(
            "message",
            "No live modules and no doctrine fit in the Fittings app.",
        )
    return base


def _historical_fit_unavailable(
    ship_type_id: int,
    *,
    request=None,
    message: str = "",
) -> dict[str, Any]:
    """Doctrine or empty response for a requested hull — never the ship they are in now."""
    hull = type_name(ship_type_id)
    base: dict[str, Any] = {
        "ship_type_id": ship_type_id,
        "ship_type_name": hull,
        "ship_name": "",
        "has_fitting": False,
        "fitting_name": "",
        "eft": "",
        "everef_url": f"https://everef.com/types/{ship_type_id}",
        "source": "none",
        "message": message
        or (
            f"No saved fit snapshot for {hull} during that fleet. "
            "Snapshots are taken each poll while in fleet (assets scope required)."
        ),
        "visual_html": "",
        "fitting_id": None,
    }
    return _merge_doctrine_fallback(base, character_id=0, ship_type_id=ship_type_id, request=request)


def fitting_payload_for_character(
    character_id: int,
    ship_type_id: int,
    *,
    request=None,
    snapshot_id: int | None = None,
    session_id: int | None = None,
    ship_name: str = "",
    first_seen=None,
    last_seen=None,
    use_live: bool = False,
) -> dict[str, Any]:
    from standing_fleet_tracker.models import ShipFitSnapshot
    from standing_fleet_tracker.services.fit_snapshots import find_best_snapshot, snapshot_payload

    if snapshot_id:
        snap = ShipFitSnapshot.objects.select_related("character").get(
            pk=snapshot_id, character__character_id=character_id
        )
        return snapshot_payload(snap, request)

    if use_live:
        return live_ship_fit_payload(
            character_id, ship_type_id_hint=ship_type_id, request=request
        )

    snap = find_best_snapshot(
        character_id,
        ship_type_id,
        session_id=session_id,
        ship_name=ship_name,
        first_seen=first_seen,
        last_seen=last_seen,
    )
    if snap:
        return snapshot_payload(snap, request)

    return _historical_fit_unavailable(ship_type_id, request=request)
