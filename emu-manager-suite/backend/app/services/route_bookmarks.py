"""Saved route bookmarks with visibility and share links."""

from __future__ import annotations

import json
from typing import Any

from sqlalchemy import or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import settings
from app.models import RouteBookmark, SsoUser
from app.services.appraisal import new_share_token


def _bookmark_out(row: RouteBookmark) -> dict[str, Any]:
    waypoints: list[int] = []
    try:
        waypoints = json.loads(row.waypoint_system_ids_json or "[]")
    except json.JSONDecodeError:
        pass
    payload: dict = {}
    try:
        payload = json.loads(row.payload_json or "{}")
    except json.JSONDecodeError:
        pass
    share_url = None
    if row.share_token:
        share_url = f"{settings.public_base_url}/map?route={row.share_token}"
    return {
        "id": row.id,
        "name": row.name,
        "origin_system": row.origin_system,
        "destination_system": row.destination_system,
        "origin_system_id": row.origin_system_id,
        "destination_system_id": row.destination_system_id,
        "jumps": row.jumps,
        "security_max": row.security_max,
        "route_mode": row.route_mode,
        "visibility": row.visibility,
        "owner_character_id": row.owner_character_id,
        "owner_character_name": row.owner_character_name,
        "corporation_id": row.corporation_id,
        "alliance_id": row.alliance_id,
        "waypoint_system_ids": waypoints,
        "route_json": json.loads(row.route_json or "[]") if row.route_json else [],
        "payload": payload,
        "share_token": row.share_token,
        "share_url": share_url,
        "created_at": row.created_at.isoformat() if row.created_at else None,
    }


def _visible_filter(viewer: SsoUser | None):
    if viewer is None:
        return or_(
            RouteBookmark.visibility.in_(("alliance", "corp")),
            RouteBookmark.owner_character_id.is_(None),
        )
    parts: list = [RouteBookmark.owner_character_id == viewer.character_id]
    if viewer.corporation_id:
        parts.append(
            (RouteBookmark.visibility == "corp") & (RouteBookmark.corporation_id == viewer.corporation_id)
        )
    if viewer.alliance_id:
        parts.append(
            (RouteBookmark.visibility == "alliance") & (RouteBookmark.alliance_id == viewer.alliance_id)
        )
    return or_(*parts)


async def list_route_bookmarks(
    session: AsyncSession,
    *,
    character_id: int | None = None,
) -> list[dict[str, Any]]:
    viewer = None
    if character_id:
        viewer = await session.scalar(select(SsoUser).where(SsoUser.character_id == character_id))
    rows = (
        await session.scalars(
            select(RouteBookmark).where(_visible_filter(viewer)).order_by(RouteBookmark.id.desc())
        )
    ).all()
    return [_bookmark_out(r) for r in rows]


async def get_route_by_share_token(session: AsyncSession, share_token: str) -> dict[str, Any] | None:
    row = await session.scalar(select(RouteBookmark).where(RouteBookmark.share_token == share_token))
    if not row:
        return None
    return _bookmark_out(row)


async def create_route_bookmark(
    session: AsyncSession,
    *,
    name: str,
    origin_system: str,
    destination_system: str,
    origin_system_id: int | None,
    destination_system_id: int | None,
    jumps: int,
    route_mode: str,
    visibility: str,
    security_max: float,
    route_names: list[str],
    waypoint_system_ids: list[int],
    payload: dict[str, Any],
    owner_character_id: int | None = None,
    owner_character_name: str = "",
    corporation_id: int | None = None,
    alliance_id: int | None = None,
) -> dict[str, Any]:
    token = new_share_token()
    row = RouteBookmark(
        name=name.strip() or f"{origin_system} → {destination_system}",
        origin_system=origin_system,
        destination_system=destination_system,
        origin_system_id=origin_system_id,
        destination_system_id=destination_system_id,
        jumps=jumps,
        route_json=json.dumps(route_names),
        security_max=security_max,
        route_mode=route_mode,
        visibility=visibility,
        payload_json=json.dumps(payload),
        waypoint_system_ids_json=json.dumps(waypoint_system_ids),
        share_token=token,
        owner_character_id=owner_character_id,
        owner_character_name=owner_character_name,
        corporation_id=corporation_id,
        alliance_id=alliance_id,
    )
    session.add(row)
    await session.flush()
    return _bookmark_out(row)


async def delete_route_bookmark(
    session: AsyncSession,
    bookmark_id: int,
    *,
    character_id: int | None = None,
) -> bool:
    row = await session.get(RouteBookmark, bookmark_id)
    if not row:
        return False
    if character_id and row.owner_character_id and row.owner_character_id != character_id:
        return False
    await session.delete(row)
    return True
