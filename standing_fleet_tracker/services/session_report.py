"""Build per-fleet session travel and ship history for UI."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime

from standing_fleet_tracker.models import (
    FleetLocationSample,
    FleetSession,
    FleetSessionShipLog,
    ShipFitSnapshot,
)
from standing_fleet_tracker.services.fit_snapshots import find_best_snapshot
from standing_fleet_tracker.services.universe import solar_system_name, type_name


@dataclass
class SystemVisit:
    solar_system_id: int
    system_name: str
    first_seen: datetime
    last_seen: datetime
    sample_count: int


@dataclass
class ShipUsage:
    ship_type_id: int
    ship_type_name: str
    ship_name: str
    first_seen: datetime
    last_seen: datetime
    has_fitting: bool
    latest_snapshot_id: int | None = None


def _fitting_ids_for_ship_types(ship_type_ids: set[int]) -> dict[int, bool]:
    if not ship_type_ids:
        return {}
    try:
        from django.apps import apps

        if not apps.is_installed("fittings"):
            return {}
        from fittings.models import Fitting

        found = set(
            Fitting.objects.filter(ship_type_type_id__in=ship_type_ids).values_list(
                "ship_type_type_id", flat=True
            )
        )
        return {tid: tid in found for tid in ship_type_ids}
    except Exception:
        return {}


def build_session_report(session: FleetSession) -> dict:
    locations = list(
        FleetLocationSample.objects.filter(session=session).order_by("recorded_at")
    )
    by_system: dict[int, SystemVisit] = {}
    for loc in locations:
        sid = loc.solar_system_id
        if sid not in by_system:
            by_system[sid] = SystemVisit(
                solar_system_id=sid,
                system_name=solar_system_name(sid),
                first_seen=loc.recorded_at,
                last_seen=loc.recorded_at,
                sample_count=1,
            )
        else:
            row = by_system[sid]
            row.last_seen = loc.recorded_at
            row.sample_count += 1

    systems = sorted(by_system.values(), key=lambda s: s.first_seen)

    ship_logs = list(
        FleetSessionShipLog.objects.filter(session=session).order_by("recorded_at")
    )
    if not ship_logs and session.last_ship_type_id:
        ship_logs = []

    ship_type_ids = {log.ship_type_id for log in ship_logs}
    if session.last_ship_type_id:
        ship_type_ids.add(session.last_ship_type_id)
    has_fit = _fitting_ids_for_ship_types(ship_type_ids)

    ships: list[ShipUsage] = []
    for log in ship_logs:
        if (
            ships
            and ships[-1].ship_type_id == log.ship_type_id
            and ships[-1].ship_name == (log.ship_name or "")
        ):
            ships[-1].last_seen = log.recorded_at
            continue
        ships.append(
            ShipUsage(
                ship_type_id=log.ship_type_id,
                ship_type_name=type_name(log.ship_type_id),
                ship_name=log.ship_name or "",
                first_seen=log.recorded_at,
                last_seen=log.recorded_at,
                has_fitting=has_fit.get(log.ship_type_id, False),
            )
        )

    if not ships and session.last_ship_type_id:
        ships.append(
            ShipUsage(
                ship_type_id=session.last_ship_type_id,
                ship_type_name=type_name(session.last_ship_type_id),
                ship_name=session.last_ship_name or "",
                first_seen=session.started_at,
                last_seen=session.ended_at or session.started_at,
                has_fitting=has_fit.get(session.last_ship_type_id, False),
            )
        )

    fit_snapshots = list(
        ShipFitSnapshot.objects.filter(session=session).order_by("recorded_at")
    )

    char_eve_id = session.character.character_id
    for ship in ships:
        snap = find_best_snapshot(
            char_eve_id,
            ship.ship_type_id,
            session_id=session.pk,
            ship_name=ship.ship_name,
            first_seen=ship.first_seen,
            last_seen=ship.last_seen,
        )
        ship.latest_snapshot_id = snap.pk if snap else None

    snapshot_rows = [
        {
            "snapshot": snap,
            "ship_type_name": type_name(snap.ship_type_id),
        }
        for snap in fit_snapshots
    ]

    return {
        "session": session,
        "systems": systems,
        "ships": ships,
        "fit_snapshots": fit_snapshots,
        "snapshot_rows": snapshot_rows,
    }
