"""Wormhole map CRUD and WebSocket broadcast."""

from __future__ import annotations

import json
import logging
from typing import Any

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.wormhole_map import WormholeConnection, WormholeMap, WormholeSystem

logger = logging.getLogger(__name__)


class WhMapConnectionManager:
    def __init__(self) -> None:
        self._rooms: dict[int, set[Any]] = {}

    async def connect(self, map_id: int, websocket: Any) -> None:
        await websocket.accept()
        self._rooms.setdefault(map_id, set()).add(websocket)

    def disconnect(self, map_id: int, websocket: Any) -> None:
        room = self._rooms.get(map_id)
        if not room:
            return
        room.discard(websocket)
        if not room:
            self._rooms.pop(map_id, None)

    async def broadcast(self, map_id: int, payload: dict) -> None:
        room = self._rooms.get(map_id)
        if not room:
            return
        dead: list[Any] = []
        for ws in room:
            try:
                await ws.send_json(payload)
            except Exception:
                dead.append(ws)
        for ws in dead:
            self.disconnect(map_id, ws)


wh_connection_manager = WhMapConnectionManager()


def _system_out(row: WormholeSystem) -> dict:
    return {
        "id": row.id,
        "map_id": row.map_id,
        "solar_system_id": row.solar_system_id,
        "system_name": row.system_name,
        "system_signature": row.system_signature,
        "wh_class": row.wh_class,
        "space_type": row.space_type,
        "effect": row.effect,
        "statics": json.loads(row.statics_json or "[]"),
        "pos_x": row.pos_x,
        "pos_y": row.pos_y,
    }


def _connection_out(row: WormholeConnection) -> dict:
    return {
        "id": row.id,
        "map_id": row.map_id,
        "source_node_id": row.source_node_id,
        "target_node_id": row.target_node_id,
        "wh_type": row.wh_type,
        "mass_status": row.mass_status,
        "eol": row.eol,
        "signature_in": row.signature_in,
        "signature_out": row.signature_out,
    }


async def load_map_topology(session: AsyncSession, map_id: int) -> dict:
    systems = (
        await session.scalars(select(WormholeSystem).where(WormholeSystem.map_id == map_id))
    ).all()
    connections = (
        await session.scalars(
            select(WormholeConnection).where(WormholeConnection.map_id == map_id)
        )
    ).all()
    return {
        "systems": [_system_out(s) for s in systems],
        "connections": [_connection_out(c) for c in connections],
    }


async def create_wh_map(session: AsyncSession, **kwargs) -> WormholeMap:
    row = WormholeMap(**kwargs)
    session.add(row)
    await session.flush()
    return row


async def add_wh_system(session: AsyncSession, map_id: int, **kwargs) -> WormholeSystem:
    statics = kwargs.pop("statics", None)
    row = WormholeSystem(map_id=map_id, statics_json=json.dumps(statics or []), **kwargs)
    session.add(row)
    await session.flush()
    return row


async def add_wh_connection(session: AsyncSession, map_id: int, **kwargs) -> WormholeConnection:
    row = WormholeConnection(map_id=map_id, **kwargs)
    session.add(row)
    await session.flush()
    return row


async def patch_wh_connection(
    session: AsyncSession,
    connection_id: int,
    *,
    mass_status: str | None = None,
    eol: bool | None = None,
    wh_type: str | None = None,
) -> WormholeConnection | None:
    row = await session.get(WormholeConnection, connection_id)
    if not row:
        return None
    if mass_status is not None:
        row.mass_status = mass_status
    if eol is not None:
        row.eol = eol
    if wh_type is not None:
        row.wh_type = wh_type
    return row
