"""Geographic 2D map layout from SDE universe coordinates (CCP map-data guide)."""

from __future__ import annotations

import logging
import math
from collections import defaultdict, deque
from typing import Any

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import SdeStargateLink, SdeSystem
from app.services.jump_drive import map_display_xy

logger = logging.getLogger(__name__)

# Normalized canvas extent for layout_x / layout_y (see get_map_atlas).
GEOGRAPHIC_LAYOUT_TARGET = 10_000.0
REFERENCE_SYSTEM_ID = 30000142  # Jita — sanity check for layout migration
NEW_EDEN_SYSTEM_ID_MIN = 30_000_000
NEW_EDEN_SYSTEM_ID_MAX = 30_999_999

REGION_SPACING = 520.0
TOPO_CONST_SPACING = 130.0
TOPO_NODE_SPACING = 38.0


def _build_adjacency(links: list[SdeStargateLink]) -> dict[int, list[int]]:
    adj: dict[int, list[int]] = defaultdict(list)
    for link in links:
        adj[link.from_system_id].append(link.to_system_id)
        adj[link.to_system_id].append(link.from_system_id)
    return adj


def _is_new_eden_system(system_id: int) -> bool:
    """K-space systems shown on the in-game map (CCP map-data ID range)."""
    return NEW_EDEN_SYSTEM_ID_MIN <= system_id <= NEW_EDEN_SYSTEM_ID_MAX


def compute_geographic_layout(
    systems: list[SdeSystem],
    *,
    target_size: float = GEOGRAPHIC_LAYOUT_TARGET,
) -> dict[int, tuple[float, float]]:
    """Project SDE x/z to 2D using CCP map-data conventions.

    Universe top-down view: X_img = X, Y_img = -Z (image Y increases downward).
    Bounding box uses New Eden (system IDs 30M–30.99M) so WH/Pochven coords do not
    compress k-space. See https://developers.eveonline.com/docs/guides/map-data/
    """
    with_coords = [s for s in systems if s.x is not None and s.z is not None]
    if not with_coords:
        return {}

    bbox_systems = [s for s in with_coords if _is_new_eden_system(s.system_id)]
    if not bbox_systems:
        bbox_systems = with_coords

    xs = [float(s.x) for s in bbox_systems]
    zs = [float(s.z) for s in bbox_systems]
    min_x, max_x = min(xs), max(xs)
    min_z, max_z = min(zs), max(zs)
    map_size = max(max_x - min_x, max_z - min_z, 1.0)

    layout: dict[int, tuple[float, float]] = {}
    for s in with_coords:
        x = float(s.x)
        z = float(s.z)
        layout[s.system_id] = (
            (x - min_x) / map_size * target_size,
            -(z - max_z) / map_size * target_size,
        )
    return layout


def _layout_matches_reference(
    layout: dict[int, tuple[float, float]],
    reference: SdeSystem,
    *,
    tolerance: float = 8.0,
) -> bool:
    expected = layout.get(reference.system_id)
    if not expected or reference.layout_x is None or reference.layout_y is None:
        return False
    return (
        abs(float(reference.layout_x) - expected[0]) <= tolerance
        and abs(float(reference.layout_y) - expected[1]) <= tolerance
    )


async def layout_uses_geographic(session: AsyncSession) -> bool:
    """True when stored layout matches CCP geographic projection."""
    rows = (await session.scalars(select(SdeSystem).where(SdeSystem.x.isnot(None)))).all()
    if len(rows) < 1000:
        return False
    reference = next((s for s in rows if s.system_id == REFERENCE_SYSTEM_ID), None)
    if not reference:
        reference = rows[0]
    geo = compute_geographic_layout(rows)
    return _layout_matches_reference(geo, reference)

def _constellation_chain_layout(
    members: list[SdeSystem],
    adjacency: dict[int, list[int]],
    origin_x: float,
    origin_y: float,
) -> dict[int, tuple[float, float]]:
    """Snake layout for systems in one constellation using stargate connectivity."""
    ids = {m.system_id for m in members}
    if not ids:
        return {}

    start = sorted(ids)[0]
    ordered: list[int] = []
    visited: set[int] = set()
    queue: deque[int] = deque([start])

    while queue:
        current = queue.popleft()
        if current in visited:
            continue
        visited.add(current)
        ordered.append(current)
        for nxt in sorted(adjacency.get(current, [])):
            if nxt in ids and nxt not in visited:
                queue.append(nxt)

    for sid in sorted(ids):
        if sid not in visited:
            ordered.append(sid)

    out: dict[int, tuple[float, float]] = {}
    cols = 5
    for i, sid in enumerate(ordered):
        row = i // cols
        col = i % cols
        if row % 2:
            col = cols - 1 - col
        out[sid] = (
            origin_x + col * TOPO_NODE_SPACING,
            origin_y + row * TOPO_NODE_SPACING * 0.85,
        )
    return out


def compute_topology_layout(
    systems: list[SdeSystem],
    adjacency: dict[int, list[int]],
) -> dict[int, tuple[float, float]]:
    """Region/constellation grid layout from stargate graph (no SDE coords required)."""
    if not systems:
        return {}

    by_region: dict[str, list[SdeSystem]] = defaultdict(list)
    for s in systems:
        by_region[s.region_name or "Unknown"].append(s)

    layout: dict[int, tuple[float, float]] = {}
    regions = sorted(by_region.keys())
    rcols = max(1, int(math.ceil(math.sqrt(len(regions)))))

    for ri, region_name in enumerate(regions):
        rcx = (ri % rcols) * REGION_SPACING
        rcy = (ri // rcols) * REGION_SPACING

        by_const: dict[str, list[SdeSystem]] = defaultdict(list)
        for s in by_region[region_name]:
            by_const[s.constellation_name or "Unknown"].append(s)

        consts = sorted(by_const.keys())
        ccols = max(1, int(math.ceil(math.sqrt(len(consts)))))
        for ci, const_name in enumerate(consts):
            cax = rcx + (ci % ccols) * TOPO_CONST_SPACING
            cay = rcy + (ci // ccols) * TOPO_CONST_SPACING
            layout.update(
                _constellation_chain_layout(by_const[const_name], adjacency, cax, cay)
            )

    return layout


async def layout_is_degenerate(session: AsyncSession) -> bool:
    """True when stored layout has too few distinct positions (all stacked)."""
    distinct = await session.scalar(
        select(func.count()).select_from(
            select(SdeSystem.layout_x, SdeSystem.layout_y)
            .where(SdeSystem.layout_x.isnot(None))
            .distinct()
            .subquery()
        )
    )
    total = await session.scalar(select(func.count()).select_from(SdeSystem)) or 0
    if not total:
        return True
    if not distinct or distinct < min(10, max(3, int(total * 0.05))):
        return True
    return False


async def apply_map_layout(session: AsyncSession) -> int:
    rows = (await session.scalars(select(SdeSystem))).all()
    if not rows:
        return 0

    links = (await session.scalars(select(SdeStargateLink))).all()
    adjacency = _build_adjacency(links)

    with_coords = [s for s in rows if s.x is not None and s.z is not None]
    layout: dict[int, tuple[float, float]] = compute_geographic_layout(with_coords)

    missing = [s for s in rows if s.system_id not in layout]
    if missing:
        layout.update(compute_topology_layout(missing, adjacency))

    updated = 0
    for s in rows:
        pos = layout.get(s.system_id)
        if not pos:
            pos = map_display_xy(s.x, s.z)
        s.layout_x = float(pos[0])
        s.layout_y = float(pos[1])
        updated += 1

    await session.flush()
    logger.info(
        "EMUMS: computed geographic map layout for %s systems (%s from SDE x/z, %s topology fallback)",
        updated,
        len(with_coords),
        len(missing),
    )
    return updated


async def map_layout_is_ready(session: AsyncSession) -> bool:
    with_layout = await session.scalar(
        select(func.count()).select_from(SdeSystem).where(SdeSystem.layout_x.isnot(None))
    )
    total = await session.scalar(select(func.count()).select_from(SdeSystem)) or 0
    if not total:
        return False
    if not with_layout or with_layout < max(1, int(total * 0.9)):
        return False
    return await layout_uses_geographic(session)


async def ensure_map_layout(session: AsyncSession) -> bool:
    total = await session.scalar(select(func.count()).select_from(SdeSystem)) or 0
    if not total:
        return False
    if await map_layout_is_ready(session):
        return False
    await apply_map_layout(session)
    return True


def system_layout_xy(sys: SdeSystem) -> tuple[float, float]:
    if sys.layout_x is not None and sys.layout_y is not None:
        lx, ly = float(sys.layout_x), float(sys.layout_y)
        if abs(lx) > 1e-6 or abs(ly) > 1e-6:
            return (lx, ly)
    if sys.x is not None and sys.z is not None:
        xy = map_display_xy(sys.x, sys.z)
        if abs(xy[0]) > 1e-6 or abs(xy[1]) > 1e-6:
            return xy
    if sys.layout_x is not None and sys.layout_y is not None:
        return (float(sys.layout_x), float(sys.layout_y))
    return map_display_xy(sys.x, sys.z)


async def get_map_atlas(session: AsyncSession) -> dict[str, Any]:
    """Compact preloaded atlas for client-side canvas map."""
    await ensure_map_layout(session)

    systems = (await session.scalars(select(SdeSystem).order_by(SdeSystem.system_id))).all()
    links = (await session.scalars(select(SdeStargateLink))).all()

    sys_rows = [
        [
            s.system_id,
            s.name,
            round(s.security, 2),
            round(system_layout_xy(s)[0], 2),
            round(system_layout_xy(s)[1], 2),
            s.region_name or "",
            s.constellation_name or "",
        ]
        for s in systems
    ]
    edge_rows = [[link.from_system_id, link.to_system_id] for link in links]

    return {
        "version": 3,
        "projection": "geographic",
        "systems": sys_rows,
        "edges": edge_rows,
        "system_count": len(sys_rows),
        "edge_count": len(edge_rows),
    }
