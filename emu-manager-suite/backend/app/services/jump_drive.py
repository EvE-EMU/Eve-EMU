"""Capital / Blops jump drive range, routing, and fuel calculations."""

from __future__ import annotations

import math
from typing import Any

from app.services.jump_ship_specs import ensure_jump_ships_loaded, get_jump_ship, list_jump_ship_specs
from app.services.sde_import import LIGHT_YEAR_METERS


def list_jump_ships() -> list[dict]:
    return list_jump_ship_specs()


def map_display_xy(x: float | None, z: float | None) -> tuple[float, float]:
    """Raw SDE x/z to map plane (CCP: X right, Y = -Z north-up on screen)."""
    if x is None or z is None:
        return (0.0, 0.0)
    return (x / 1e14, -(z / 1e14))


def _layout_xy(
    system_id: int,
    coords: dict[int, tuple[float, float, float]],
    display_xy: dict[int, tuple[float, float]] | None,
) -> tuple[float, float]:
    if display_xy and system_id in display_xy:
        return display_xy[system_id]
    cx, _cy, cz = coords[system_id]
    return map_display_xy(cx, cz)


def distance_ly(
    a: int,
    b: int,
    coords: dict[int, tuple[float, float, float]],
) -> float:
    ax, ay, az = coords[a]
    bx, by, bz = coords[b]
    meters = math.sqrt((ax - bx) ** 2 + (ay - by) ** 2 + (az - bz) ** 2)
    return meters / LIGHT_YEAR_METERS


def effective_range_ly(base: float, jump_drive_calibration: int) -> float:
    cal = max(0, min(5, jump_drive_calibration))
    return base * (1.0 + 0.2 * cal)


def fuel_for_jump(
    *,
    distance_ly: float,
    fuel_per_ly: float,
    jump_fuel_conservation: int = 0,
    jump_freighters: int = 0,
    is_jump_freighter: bool = False,
) -> int:
    """EVE client formula: D × F × (1 − 0.1×JFC) × (1 − 0.1×JF for JFs only)."""
    if distance_ly <= 0 or fuel_per_ly <= 0:
        return 0
    jfc = max(0, min(5, jump_fuel_conservation))
    jf = max(0, min(5, jump_freighters)) if is_jump_freighter else 0
    raw = distance_ly * fuel_per_ly * (1.0 - 0.1 * jfc) * (1.0 - 0.1 * jf)
    return max(1, int(math.ceil(raw)))


def _heuristic_ly(
    system_id: int,
    destination: int,
    coords: dict[int, tuple[float, float, float]],
    max_range: float,
) -> float:
    if system_id not in coords or destination not in coords or max_range <= 0:
        return 0.0
    return distance_ly(system_id, destination, coords) / max_range


def _find_jump_path(
    *,
    origin: int,
    destination: int,
    max_range: float,
    coords: dict[int, tuple[float, float, float]],
    max_hops: int = 25,
) -> list[int] | None:
    """A* pathfinding over jump-drive range constraints (minimize hop count)."""
    if origin not in coords or destination not in coords:
        return None
    if origin == destination:
        return [origin]
    if distance_ly(origin, destination, coords) <= max_range:
        return [origin, destination]

    import heapq

    open_set: list[tuple[float, int, list[int]]] = []
    heapq.heappush(open_set, (_heuristic_ly(origin, destination, coords, max_range), 0, [origin]))
    best_g: dict[int, int] = {origin: 0}

    while open_set:
        _f, g, path = heapq.heappop(open_set)
        current = path[-1]
        if len(path) > max_hops:
            continue
        if current == destination:
            return path
        for cand in coords:
            if cand in path:
                continue
            if distance_ly(current, cand, coords) > max_range:
                continue
            new_g = g + 1
            if best_g.get(cand, max_hops + 1) <= new_g:
                continue
            best_g[cand] = new_g
            new_path = path + [cand]
            h = _heuristic_ly(cand, destination, coords, max_range)
            heapq.heappush(open_set, (new_g + h, new_g, new_path))
    return None


def build_waypoint_string(
    path: list[int],
    names: dict[int, str],
) -> str:
    """In-game friendly waypoint list (one system per line)."""
    lines = [names.get(sid, str(sid)) for sid in path]
    return "\n".join(lines)


def plan_jump_route(
    *,
    ship_slug: str,
    origin_system_id: int,
    destination_system_id: int,
    jump_drive_calibration: int = 0,
    jump_fuel_conservation: int = 0,
    jump_freighters: int = 0,
    coords: dict[int, tuple[float, float, float]],
    system_names: dict[int, str] | None = None,
    system_security: dict[int, float] | None = None,
    display_xy: dict[int, tuple[float, float]] | None = None,
) -> dict[str, Any]:
    ensure_jump_ships_loaded()
    ship = get_jump_ship(ship_slug)
    if not ship:
        return {"error": "unknown_ship"}

    if not coords:
        return {"error": "no_sde_coords", "message": "Map coordinates not loaded. Import SDE data first."}

    names = system_names or {}
    sec = system_security or {}

    if origin_system_id not in coords:
        return {"error": "unknown_system", "message": f"Origin system {origin_system_id} has no SDE coordinates."}
    if destination_system_id not in coords:
        return {"error": "unknown_system", "message": f"Destination system {destination_system_id} has no SDE coordinates."}

    max_range = effective_range_ly(ship["base_range_ly"], jump_drive_calibration)

    if origin_system_id == destination_system_id:
        x, y = _layout_xy(origin_system_id, coords, display_xy)
        return {
            "ship": ship["name"],
            "jumps": 0,
            "total_distance_ly": 0.0,
            "total_fuel": 0,
            "fuel_type": ship["fuel_type"],
            "effective_range_ly": round(max_range, 2),
            "legs": [],
            "systems": [
                {
                    "system_id": origin_system_id,
                    "name": names.get(origin_system_id, str(origin_system_id)),
                    "security": sec.get(origin_system_id, 0.0),
                    "x": x,
                    "y": y,
                }
            ],
            "waypoint_string": names.get(origin_system_id, str(origin_system_id)),
            "midpoint_systems": [],
        }

    path = _find_jump_path(
        origin=origin_system_id,
        destination=destination_system_id,
        max_range=max_range,
        coords=coords,
    )
    if not path:
        direct = distance_ly(origin_system_id, destination_system_id, coords)
        return {
            "error": "no_jump_route",
            "ship": ship["name"],
            "effective_range_ly": round(max_range, 2),
            "direct_distance_ly": round(direct, 2),
            "message": (
                f"No jump route found. Direct distance is {direct:.1f} ly "
                f"but max jump range is {max_range:.1f} ly."
            ),
        }

    legs: list[dict] = []
    total_dist = 0.0
    total_fuel = 0
    for i in range(len(path) - 1):
        a, b = path[i], path[i + 1]
        d = distance_ly(a, b, coords)
        fuel = fuel_for_jump(
            distance_ly=d,
            fuel_per_ly=ship["fuel_per_ly"],
            jump_fuel_conservation=jump_fuel_conservation,
            jump_freighters=jump_freighters,
            is_jump_freighter=ship["is_jump_freighter"],
        )
        legs.append(
            {
                "from_system_id": a,
                "to_system_id": b,
                "from_name": names.get(a, str(a)),
                "to_name": names.get(b, str(b)),
                "distance_ly": round(d, 2),
                "fuel": fuel,
            }
        )
        total_dist += d
        total_fuel += fuel

    systems_out = []
    for sid in path:
        x, y = _layout_xy(sid, coords, display_xy)
        systems_out.append(
            {
                "system_id": sid,
                "name": names.get(sid, str(sid)),
                "security": sec.get(sid, 0.0),
                "x": x,
                "y": y,
            }
        )

    waypoint_string = build_waypoint_string(path, names)
    return {
        "ship": ship["name"],
        "ship_slug": ship_slug,
        "category": ship["category"],
        "jumps": len(legs),
        "total_distance_ly": round(total_dist, 2),
        "total_fuel": total_fuel,
        "fuel_type": ship["fuel_type"],
        "fuel_type_id": ship["fuel_type_id"],
        "effective_range_ly": round(max_range, 2),
        "base_range_ly": ship["base_range_ly"],
        "jump_drive_calibration": jump_drive_calibration,
        "jump_fuel_conservation": jump_fuel_conservation,
        "jump_freighters": jump_freighters if ship["is_jump_freighter"] else None,
        "fuel_per_ly": ship["fuel_per_ly"],
        "direct_distance_ly": round(distance_ly(origin_system_id, destination_system_id, coords), 2),
        "legs": legs,
        "systems": systems_out,
        "waypoint_string": waypoint_string,
        "midpoint_systems": [
            names.get(sid, str(sid)) for sid in path[1:-1]
        ],
    }


def jump_range_systems(
    *,
    ship_slug: str,
    origin_system_id: int,
    jump_drive_calibration: int = 0,
    coords: dict[int, tuple[float, float, float]],
    system_names: dict[int, str] | None = None,
    system_security: dict[int, float] | None = None,
    display_xy: dict[int, tuple[float, float]] | None = None,
) -> dict[str, Any]:
    ensure_jump_ships_loaded()
    ship = get_jump_ship(ship_slug)
    if not ship:
        return {"error": "unknown_ship"}

    if origin_system_id not in coords:
        return {"error": "unknown_system", "systems": []}

    names = system_names or {}
    sec = system_security or {}
    max_range = effective_range_ly(ship["base_range_ly"], jump_drive_calibration)

    in_range = []
    for sid in coords:
        d = distance_ly(origin_system_id, sid, coords)
        if d <= max_range:
            x, y = _layout_xy(sid, coords, display_xy)
            in_range.append(
                {
                    "system_id": sid,
                    "name": names.get(sid, str(sid)),
                    "security": sec.get(sid, 0.0),
                    "distance_ly": round(d, 2),
                    "x": x,
                    "y": y,
                }
            )
    in_range.sort(key=lambda item: item["distance_ly"])

    return {
        "ship": ship["name"],
        "effective_range_ly": round(max_range, 2),
        "fuel_type": ship["fuel_type"],
        "origin_system_id": origin_system_id,
        "systems": in_range,
    }
