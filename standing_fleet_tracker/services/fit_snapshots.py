"""Persist and query point-in-time ship fits (90-day retention)."""

from __future__ import annotations

import hashlib
import json
import logging
from datetime import timedelta
from typing import Any

from django.utils import timezone

from standing_fleet_tracker import app_settings
from standing_fleet_tracker.models import FleetSession, ShipFitSnapshot
from standing_fleet_tracker.services import esi as esi_api
from standing_fleet_tracker.services.scopes import missing_scopes_for_token
from standing_fleet_tracker.services.ship_fit import (
    ASSETS_SCOPE,
    _fitted_items_on_ship,
    build_eft_from_fitted_items,
)
from standing_fleet_tracker.services.universe import type_name

logger = logging.getLogger(__name__)


def modules_fingerprint(modules: list[dict[str, Any]]) -> str:
    normalized = sorted(
        [
            {
                "flag": str(m.get("flag") or m.get("location_flag") or ""),
                "type_id": int(m["type_id"]),
                "quantity": int(m.get("quantity") or 1),
            }
            for m in modules
        ],
        key=lambda row: (row["flag"], row["type_id"]),
    )
    payload = json.dumps(normalized, sort_keys=True, separators=(",", ":"))
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()


def _modules_from_assets(assets: list[dict], ship_item_id: int) -> list[dict[str, Any]]:
    rows = _fitted_items_on_ship(assets, ship_item_id)
    return [
        {
            "flag": str(r.get("location_flag") or ""),
            "type_id": int(r["type_id"]),
            "quantity": int(r.get("quantity") or 1),
        }
        for r in rows
    ]


def record_fit_snapshot_for_character(
    character,
    token,
    session: FleetSession | None,
    *,
    in_standing_fleet: bool = False,
) -> ShipFitSnapshot | None:
    """Capture fitted modules while in fleet; skip duplicate consecutive fingerprints."""
    if ASSETS_SCOPE in missing_scopes_for_token(token):
        return None

    ship_status, ship = esi_api.get_character_ship(character.character_id, token)
    if ship_status != 200 or not ship:
        return None

    ship_item_id = int(ship["ship_item_id"])
    ship_type_id = int(ship["ship_type_id"])
    ship_name = str(ship.get("ship_name") or "")

    assets = esi_api.get_character_assets(character.character_id, token)
    if assets is None:
        return None

    modules = _modules_from_assets(assets, ship_item_id)
    fingerprint = modules_fingerprint(modules)

    last = (
        ShipFitSnapshot.objects.filter(character=character, ship_item_id=ship_item_id)
        .order_by("-recorded_at")
        .first()
    )
    if last and last.modules_fingerprint == fingerprint:
        return last

    eft = build_eft_from_fitted_items(
        ship_type_id,
        ship_name=ship_name,
        fitted_items=[{"location_flag": m["flag"], "type_id": m["type_id"], "quantity": m["quantity"]} for m in modules],
    )

    return ShipFitSnapshot.objects.create(
        character=character,
        session=session,
        ship_item_id=ship_item_id,
        ship_type_id=ship_type_id,
        ship_name=ship_name,
        modules_json=modules,
        modules_fingerprint=fingerprint,
        eft_text=eft,
        in_standing_fleet=in_standing_fleet,
        recorded_at=timezone.now(),
    )


def purge_old_snapshots() -> int:
    cutoff = timezone.now() - timedelta(days=app_settings.SFT_FIT_SNAPSHOT_RETENTION_DAYS)
    deleted, _ = ShipFitSnapshot.objects.filter(recorded_at__lt=cutoff).delete()
    return deleted


def snapshot_payload(snapshot: ShipFitSnapshot, request=None) -> dict[str, Any]:
    from standing_fleet_tracker.services.visual_fit import render_visual_fitting_html

    flagged = [{"flag": m["flag"], "type_id": m["type_id"]} for m in snapshot.modules_json]
    visual_html = ""
    if request:
        visual_html = render_visual_fitting_html(
            request,
            ship_type_id=snapshot.ship_type_id,
            fit_name=snapshot.ship_name or type_name(snapshot.ship_type_id),
            flagged_rows=flagged,
        )
    return {
        "snapshot_id": snapshot.pk,
        "recorded_at": snapshot.recorded_at.isoformat(),
        "ship_type_id": snapshot.ship_type_id,
        "ship_type_name": type_name(snapshot.ship_type_id),
        "ship_name": snapshot.ship_name,
        "has_fitting": bool(snapshot.eft_text),
        "fitting_name": f"Snapshot {snapshot.recorded_at:%Y-%m-%d %H:%M}",
        "eft": snapshot.eft_text,
        "everef_url": f"https://everef.com/types/{snapshot.ship_type_id}",
        "source": "snapshot",
        "message": "",
        "visual_html": visual_html,
        "fitting_id": None,
    }


def snapshots_for_session(session: FleetSession):
    return ShipFitSnapshot.objects.filter(session=session).order_by("recorded_at")


def snapshots_for_ship_name(character, ship_name: str, *, start=None, end=None):
    qs = ShipFitSnapshot.objects.filter(character=character, ship_name__iexact=ship_name.strip())
    if start:
        qs = qs.filter(recorded_at__gte=start)
    if end:
        qs = qs.filter(recorded_at__lte=end)
    return qs.order_by("recorded_at")


def find_best_snapshot(
    character_id: int,
    ship_type_id: int,
    *,
    session_id: int | None = None,
    ship_name: str = "",
    first_seen=None,
    last_seen=None,
) -> ShipFitSnapshot | None:
    """Pick the snapshot from when this hull was flown, not the character's current ship."""
    qs = ShipFitSnapshot.objects.filter(
        character__character_id=character_id,
        ship_type_id=ship_type_id,
    )
    if session_id:
        qs = qs.filter(session_id=session_id)

    name = (ship_name or "").strip()
    if name:
        named = qs.filter(ship_name__iexact=name)
        if named.exists():
            qs = named

    if first_seen is not None and last_seen is not None:
        in_window = qs.filter(
            recorded_at__gte=first_seen,
            recorded_at__lte=last_seen,
        )
        snap = in_window.order_by("-recorded_at").first()
        if snap:
            return snap
        snap = qs.filter(recorded_at__lte=last_seen).order_by("-recorded_at").first()
        if snap:
            return snap

    return qs.order_by("-recorded_at").first()
