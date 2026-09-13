"""Stargate routing, jump ranges, and route planning."""

from __future__ import annotations

from collections import deque
from typing import Any

from sqlalchemy import or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import SdeStargateLink, SdeSystem
from app.services.map_layout import system_layout_xy


def system_coords_map(systems: dict[int, SdeSystem]) -> dict[int, tuple[float, float, float]]:
    out: dict[int, tuple[float, float, float]] = {}
    for sid, sys in systems.items():
        if sys.x is not None and sys.y is not None and sys.z is not None:
            out[sid] = (sys.x, sys.y, sys.z)
    return out


def system_display_map(systems: dict[int, SdeSystem]) -> dict[int, tuple[float, float]]:
    out: dict[int, tuple[float, float]] = {}
    for sid, sys in systems.items():
        if sys.x is not None and sys.z is not None:
            out[sid] = system_layout_xy(sys)
    return out


def system_node_dict(sys: SdeSystem) -> dict[str, Any]:
    x, y = system_layout_xy(sys)
    return {
        "system_id": sys.system_id,
        "name": sys.name,
        "security": sys.security,
        "region_name": sys.region_name,
        "constellation_name": sys.constellation_name,
        "x": x,
        "y": y,
    }


async def search_systems(session: AsyncSession, query: str, *, limit: int = 40) -> list[dict]:
    q = (query or "").strip()
    if q.isdigit():
        row = await session.scalar(select(SdeSystem).where(SdeSystem.system_id == int(q)))
        if row:
            return [system_node_dict(row)]
    if not q:
        rows = (await session.scalars(select(SdeSystem).order_by(SdeSystem.name).limit(limit))).all()
    else:
        pattern = f"%{q}%"
        rows = (
            await session.scalars(
                select(SdeSystem)
                .where(or_(SdeSystem.name.ilike(pattern), SdeSystem.region_name.ilike(pattern)))
                .order_by(SdeSystem.name)
                .limit(limit)
            )
        ).all()
    return [system_node_dict(r) for r in rows]


async def _adjacency(session: AsyncSession) -> dict[int, set[int]]:
    links = (await session.scalars(select(SdeStargateLink))).all()
    adj: dict[int, set[int]] = {}
    for link in links:
        adj.setdefault(link.from_system_id, set()).add(link.to_system_id)
        adj.setdefault(link.to_system_id, set()).add(link.from_system_id)
    return adj


async def _system_map(session: AsyncSession) -> dict[int, SdeSystem]:
    rows = (await session.scalars(select(SdeSystem))).all()
    return {r.system_id: r for r in rows}


async def _bfs_segment(
    adj: dict[int, set[int]],
    systems: dict[int, SdeSystem],
    origin_system_id: int,
    destination_system_id: int,
    *,
    max_security: float,
    avoid_low_sec: bool,
) -> dict[str, Any] | None:
    if origin_system_id == destination_system_id:
        sys = systems.get(origin_system_id)
        return {"path_ids": [origin_system_id], "route": [sys.name if sys else str(origin_system_id)]}

    sec_min = 0.5 if avoid_low_sec else None
    queue: deque[tuple[int, list[int]]] = deque([(origin_system_id, [origin_system_id])])
    visited = {origin_system_id}

    while queue:
        current, path = queue.popleft()
        for nxt in adj.get(current, set()):
            if nxt in visited:
                continue
            sys = systems.get(nxt)
            if not sys:
                continue
            if sec_min is not None and sys.security < sec_min:
                continue
            if sec_min is None and sys.security > max_security:
                continue
            visited.add(nxt)
            new_path = path + [nxt]
            if nxt == destination_system_id:
                return {
                    "path_ids": new_path,
                    "route": [systems[s].name for s in new_path],
                }
            queue.append((nxt, new_path))
    return None


async def plan_route(
    session: AsyncSession,
    *,
    origin_system_id: int,
    destination_system_id: int,
    max_security: float = 1.0,
    avoid_low_sec: bool = False,
    waypoint_system_ids: list[int] | None = None,
) -> dict[str, Any]:
    if origin_system_id == destination_system_id and not waypoint_system_ids:
        sys = await session.get(SdeSystem, origin_system_id)
        return {
            "jumps": 0,
            "route": [sys.name if sys else str(origin_system_id)],
            "systems": [system_node_dict(sys)] if sys else [],
            "edges": [],
            "waypoint_system_ids": [],
        }

    adj = await _adjacency(session)
    systems = await _system_map(session)
    if origin_system_id not in systems or destination_system_id not in systems:
        return {"error": "unknown_system", "jumps": 0, "route": [], "systems": []}

    waypoints = [origin_system_id]
    for sid in waypoint_system_ids or []:
        if sid not in waypoints:
            waypoints.append(sid)
    if destination_system_id not in waypoints:
        waypoints.append(destination_system_id)

    full_path: list[int] = []
    total_jumps = 0
    all_edges: list[dict[str, int]] = []

    for i in range(len(waypoints) - 1):
        segment = await _bfs_segment(
            adj,
            systems,
            waypoints[i],
            waypoints[i + 1],
            max_security=max_security,
            avoid_low_sec=avoid_low_sec,
        )
        if not segment:
            a_name = systems[waypoints[i]].name if waypoints[i] in systems else str(waypoints[i])
            b_name = systems[waypoints[i + 1]].name if waypoints[i + 1] in systems else str(waypoints[i + 1])
            return {
                "error": "no_route",
                "jumps": 0,
                "route": [],
                "systems": [],
                "message": f"No route between {a_name} and {b_name}",
            }
        seg_ids = segment["path_ids"]
        if full_path:
            full_path.extend(seg_ids[1:])
        else:
            full_path.extend(seg_ids)
        total_jumps += len(seg_ids) - 1
        all_edges.extend(
            {"from_system_id": seg_ids[j], "to_system_id": seg_ids[j + 1]}
            for j in range(len(seg_ids) - 1)
        )

    dock_stops = [sid for sid in (waypoint_system_ids or []) if sid in full_path]
    return {
        "jumps": total_jumps,
        "route": [systems[s].name for s in full_path],
        "systems": [system_node_dict(systems[s]) for s in full_path],
        "edges": all_edges,
        "waypoint_system_ids": waypoint_system_ids or [],
        "dock_stops_on_route": dock_stops,
    }


async def jump_range(
    session: AsyncSession,
    *,
    origin_system_id: int,
    jump_range: int,
    max_security: float = 1.0,
) -> dict[str, Any]:
    adj = await _adjacency(session)
    systems = await _system_map(session)
    if origin_system_id not in systems:
        return {"error": "unknown_system", "systems": []}

    visited: dict[int, int] = {origin_system_id: 0}
    queue: deque[tuple[int, int]] = deque([(origin_system_id, 0)])

    while queue:
        current, depth = queue.popleft()
        if depth >= jump_range:
            continue
        for nxt in adj.get(current, set()):
            if nxt in visited:
                continue
            sys = systems.get(nxt)
            if not sys:
                continue
            if sys.security > max_security:
                continue
            visited[nxt] = depth + 1
            queue.append((nxt, depth + 1))

    out = []
    for sid, jumps in sorted(visited.items(), key=lambda x: (x[1], systems[x[0]].name)):
        sys = systems[sid]
        row = system_node_dict(sys)
        row["jumps_from_origin"] = jumps
        out.append(row)
    return {"origin_system_id": origin_system_id, "jump_range": jump_range, "systems": out}


async def get_map_status(session: AsyncSession) -> dict[str, Any]:
    """Map coverage summary for UI (full SDE vs demo pocket)."""
    from sqlalchemy import func

    from app.services.map_layout import map_layout_is_ready

    total = await session.scalar(select(func.count()).select_from(SdeSystem)) or 0
    with_coords = await session.scalar(
        select(func.count()).select_from(SdeSystem).where(SdeSystem.x.isnot(None))
    ) or 0
    with_layout = await session.scalar(
        select(func.count()).select_from(SdeSystem).where(SdeSystem.layout_x.isnot(None))
    ) or 0
    links = await session.scalar(select(func.count()).select_from(SdeStargateLink)) or 0
    full_sde = with_coords >= 8000
    return {
        "systems_total": total,
        "systems_with_coords": with_coords,
        "systems_with_layout": with_layout,
        "stargate_links": links,
        "full_sde_loaded": full_sde,
        "jump_drive_ready": with_coords > 0,
        "layout_ready": await map_layout_is_ready(session),
    }


async def get_map_graph(session: AsyncSession, *, limit: int = 500) -> dict[str, Any]:
    """Stargate graph for visual map rendering (subset for performance)."""
    systems = await _system_map(session)
    links = (await session.scalars(select(SdeStargateLink).limit(limit * 3))).all()
    node_ids: set[int] = set()
    edges: list[dict[str, int]] = []
    for link in links:
        if link.from_system_id in systems and link.to_system_id in systems:
            node_ids.add(link.from_system_id)
            node_ids.add(link.to_system_id)
            edges.append({"from_system_id": link.from_system_id, "to_system_id": link.to_system_id})
        if len(edges) >= limit:
            break

    nodes = [system_node_dict(systems[sid]) for sid in sorted(node_ids, key=lambda i: systems[i].name)]
    return {"nodes": nodes, "edges": edges, "truncated": len(links) >= limit}
