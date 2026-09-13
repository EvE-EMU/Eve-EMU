"""Map navigation — jump routes and wormhole chain mapping."""

from __future__ import annotations

import json
from contextlib import asynccontextmanager

from fastapi import APIRouter, Depends, HTTPException, WebSocket, WebSocketDisconnect
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.session import get_db, get_session_factory
from app.models.tools import SdeSystem
from app.models.wormhole_map import WormholeMap, WormholeSystem
from app.schemas.map import (
    JumpRouteRequest,
    WhConnectionCreate,
    WhConnectionPatch,
    WhMapCreate,
    WhSystemCreate,
)
from app.services.jump_drive import list_jump_ships, plan_jump_route
from app.services.map_jump import resolve_ship_slug, resolve_system_id
from app.services.route_planner import system_coords_map, system_display_map
from app.services.wormhole_map import (
    _connection_out,
    _system_out,
    add_wh_connection,
    add_wh_system,
    create_wh_map,
    load_map_topology,
    patch_wh_connection,
    wh_connection_manager,
)

router = APIRouter(prefix="/map", tags=["Map"])


@asynccontextmanager
async def _ws_session():
    factory = get_session_factory()
    session = factory()
    try:
        yield session
    finally:
        await session.close()


async def _system_map_for_jump(db: AsyncSession) -> dict:
    rows = (await db.scalars(select(SdeSystem))).all()
    return {r.system_id: r for r in rows}


@router.post("/jump-route")
async def jump_route(body: JumpRouteRequest, db: AsyncSession = Depends(get_db)) -> dict:
    """Capital jump drive route planner (Dotlan-style)."""
    origin_id = await resolve_system_id(db, body.origin)
    dest_id = await resolve_system_id(db, body.destination)
    if not origin_id:
        raise HTTPException(400, detail=f"Unknown origin system: {body.origin}")
    if not dest_id:
        raise HTTPException(400, detail=f"Unknown destination system: {body.destination}")

    slug = resolve_ship_slug(ship_class=body.ship_class, ship_slug=body.ship_slug)
    if not slug:
        raise HTTPException(400, detail="Unknown ship_class or ship_slug")

    systems = await _system_map_for_jump(db)
    coords = system_coords_map(systems)
    display = system_display_map(systems)
    names = {sid: s.name for sid, s in systems.items()}
    sec = {sid: s.security for sid, s in systems.items()}

    return plan_jump_route(
        ship_slug=slug,
        origin_system_id=origin_id,
        destination_system_id=dest_id,
        jump_drive_calibration=body.jump_drive_calibration,
        jump_fuel_conservation=body.jump_fuel_conservation,
        jump_freighters=body.jump_freighters,
        coords=coords,
        system_names=names,
        system_security=sec,
        display_xy=display,
    )


@router.get("/jump-ships")
async def jump_ships() -> list[dict]:
    return list_jump_ships()


@router.get("/wh/maps")
async def list_wh_maps(db: AsyncSession = Depends(get_db)) -> list[dict]:
    rows = (await db.scalars(select(WormholeMap).order_by(WormholeMap.updated_at.desc()))).all()
    return [
        {
            "id": m.id,
            "name": m.name,
            "creator_character_id": m.creator_character_id,
            "creator_character_name": m.creator_character_name,
            "alliance_id": m.alliance_id,
            "active_tracking_character_id": m.active_tracking_character_id,
        }
        for m in rows
    ]


@router.post("/wh/maps")
async def create_map(body: WhMapCreate, db: AsyncSession = Depends(get_db)) -> dict:
    row = await create_wh_map(db, **body.model_dump())
    await db.commit()
    return {"id": row.id, "name": row.name}


@router.get("/wh/maps/{map_id}")
async def get_wh_map(map_id: int, db: AsyncSession = Depends(get_db)) -> dict:
    row = await db.get(WormholeMap, map_id)
    if not row:
        raise HTTPException(404, detail="Map not found")
    topo = await load_map_topology(db, map_id)
    return {"id": row.id, "name": row.name, **topo}


@router.post("/wh/maps/{map_id}/systems")
async def add_system(map_id: int, body: WhSystemCreate, db: AsyncSession = Depends(get_db)) -> dict:
    if not await db.get(WormholeMap, map_id):
        raise HTTPException(404, detail="Map not found")
    data = body.model_dump()
    statics = data.pop("statics", [])
    row = await add_wh_system(db, map_id, statics=statics, **data)
    await db.commit()
    payload = {"event": "system_added", "system": _system_out(row)}
    await wh_connection_manager.broadcast(map_id, payload)
    return payload["system"]


@router.post("/wh/maps/{map_id}/connections")
async def add_connection(
    map_id: int, body: WhConnectionCreate, db: AsyncSession = Depends(get_db)
) -> dict:
    if not await db.get(WormholeMap, map_id):
        raise HTTPException(404, detail="Map not found")
    row = await add_wh_connection(db, map_id, **body.model_dump())
    await db.commit()
    payload = {"event": "connection_added", "connection": _connection_out(row)}
    await wh_connection_manager.broadcast(map_id, payload)
    return payload["connection"]


@router.patch("/wh/connections/{connection_id}")
async def update_connection(
    connection_id: int, body: WhConnectionPatch, db: AsyncSession = Depends(get_db)
) -> dict:
    row = await patch_wh_connection(
        db,
        connection_id,
        mass_status=body.mass_status,
        eol=body.eol,
        wh_type=body.wh_type,
    )
    if not row:
        raise HTTPException(404, detail="Connection not found")
    await db.commit()
    payload = {"event": "connection_updated", "connection": _connection_out(row)}
    await wh_connection_manager.broadcast(row.map_id, payload)
    return payload["connection"]


@router.delete("/wh/systems/{node_id}")
async def delete_system(node_id: int, db: AsyncSession = Depends(get_db)) -> dict:
    row = await db.get(WormholeSystem, node_id)
    if not row:
        raise HTTPException(404, detail="System not found")
    map_id = row.map_id
    await db.delete(row)
    await db.commit()
    payload = {"event": "system_deleted", "node_id": node_id}
    await wh_connection_manager.broadcast(map_id, payload)
    return payload


@router.websocket("/wh/stream/{map_id}")
async def wh_stream(websocket: WebSocket, map_id: int) -> None:
    await wh_connection_manager.connect(map_id, websocket)
    try:
        async with _ws_session() as db:
            topo = await load_map_topology(db, map_id)
            await websocket.send_json({"event": "snapshot", **topo})
        while True:
            raw = await websocket.receive_text()
            try:
                msg = json.loads(raw)
            except json.JSONDecodeError:
                continue
            if msg.get("type") == "ping":
                await websocket.send_json({"type": "pong"})
    except WebSocketDisconnect:
        pass
    finally:
        wh_connection_manager.disconnect(map_id, websocket)
