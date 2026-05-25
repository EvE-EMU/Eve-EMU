"""Push intel into Wanderer via the public Map API (and optional DB ping rows)."""

from __future__ import annotations

import json
import logging
from typing import Any

import httpx
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine

from app.config import settings
from app.parser import ParsedEntity, ParsedIntelLine, portrait_url_for

logger = logging.getLogger(__name__)

# Wanderer MapSystem.status (lib/wanderer_app/api/map_system.ex)
STATUS_UNKNOWN = 0
STATUS_WARNING = 2
STATUS_TARGET_PRIMARY = 3
STATUS_DANGEROUS_PRIMARY = 5

_wanderer_engine = None


def wanderer_sync_enabled() -> bool:
    return bool(settings.wanderer_sync and settings.wanderer_api_token)


def _auth_headers() -> dict[str, str]:
    return {
        "Authorization": f"Bearer {settings.wanderer_api_token}",
        "Content-Type": "application/json",
    }


def _api_url(path: str) -> str:
    base = settings.wanderer_base_url.rstrip("/")
    return f"{base}{path}"


def _format_description(line: ParsedIntelLine) -> str:
    parts: list[str] = []
    for ent in line.entities:
        if ent.entity_type == "character":
            url = portrait_url_for(ent.entity_type, ent.entity_id) or ""
            parts.append(f"{ent.name} ({url})" if url else ent.name)
        elif ent.entity_type in {"corporation", "alliance"}:
            parts.append(ent.name)
    body = " · ".join(parts) if parts else line.intel_text
    prefix = f"[{line.channel}]"
    if line.inferred_system:
        prefix = f"{prefix} (last known system)"
    return f"{prefix} {body}".strip()


def _merge_labels(existing: str | None, new_tags: list[str]) -> str:
    data: dict[str, Any]
    if existing:
        try:
            data = json.loads(existing)
        except json.JSONDecodeError:
            data = {"customLabel": "", "labels": []}
    else:
        data = {"customLabel": "", "labels": []}
    labels = data.get("labels")
    if not isinstance(labels, list):
        labels = []
    for tag in new_tags:
        if tag and tag not in labels:
            labels.append(tag)
    data["labels"] = labels
    return json.dumps(data)


async def _get_existing_labels(session: AsyncSession | None, solar_system_id: int) -> str | None:
    if not session or not settings.wanderer_database_url:
        return None
    eng = _wanderer_engine_instance()
    async with eng.connect() as conn:
        row = await conn.execute(
            text(
                "SELECT labels FROM map_system_v1 "
                "WHERE map_id = (SELECT id FROM maps_v1 WHERE slug = :slug LIMIT 1) "
                "AND solar_system_id = :sid LIMIT 1"
            ),
            {"slug": settings.wanderer_map_slug, "sid": solar_system_id},
        )
        fetched = row.first()
        return fetched[0] if fetched else None


def _wanderer_engine_instance():
    global _wanderer_engine
    if _wanderer_engine is None and settings.wanderer_database_url:
        _wanderer_engine = create_async_engine(settings.wanderer_database_url, pool_pre_ping=True)
    return _wanderer_engine


async def sync_intel_line(
    line: ParsedIntelLine,
    *,
    wanderer_session: AsyncSession | None = None,
    extra_tags: list[str] | None = None,
) -> dict[str, Any]:
    """Mark a Wanderer map system as hot intel (status + description + labels)."""
    if not wanderer_sync_enabled():
        return {"skipped": True, "reason": "wanderer sync disabled or missing API token"}

    tags = list(extra_tags or [])
    tags.append(f"intel:{line.channel}")

    existing_labels = await _get_existing_labels(wanderer_session, line.solar_system_id)
    labels = _merge_labels(existing_labels, tags)

    payload = {
        "status": STATUS_DANGEROUS_PRIMARY,
        "description": _format_description(line),
        "labels": labels,
        "visible": True,
    }

    url = _api_url(
        f"/api/maps/{settings.wanderer_map_slug}/systems/{line.solar_system_id}"
    )
    try:
        async with httpx.AsyncClient(timeout=20.0) as client:
            resp = await client.put(url, headers=_auth_headers(), json=payload)
            if resp.status_code == 404:
                create_url = _api_url(f"/api/maps/{settings.wanderer_map_slug}/systems")
                create_payload = {
                    "solar_system_id": line.solar_system_id,
                    "solar_system_name": line.solar_system_name,
                    **payload,
                }
                resp = await client.post(create_url, headers=_auth_headers(), json=create_payload)
            resp.raise_for_status()
            result = resp.json() if resp.content else {}
    except Exception as exc:
        logger.exception("Wanderer system sync failed for %s", line.solar_system_name)
        return {"ok": False, "error": str(exc)}

    ping_result = await _maybe_db_ping(line)
    return {"ok": True, "system": line.solar_system_id, "wanderer": result, "db_ping": ping_result}


async def clear_intel_system(solar_system_id: int) -> dict[str, Any]:
    """Revert Wanderer system status when intel TTL expires."""
    if not wanderer_sync_enabled():
        return {"skipped": True}

    url = _api_url(f"/api/maps/{settings.wanderer_map_slug}/systems/{solar_system_id}")
    try:
        async with httpx.AsyncClient(timeout=20.0) as client:
            resp = await client.put(
                url,
                headers=_auth_headers(),
                json={"status": STATUS_UNKNOWN, "description": ""},
            )
            if resp.status_code == 404:
                return {"ok": True, "missing": True}
            resp.raise_for_status()
    except Exception as exc:
        logger.warning("Wanderer clear failed for %s: %s", solar_system_id, exc)
        return {"ok": False, "error": str(exc)}
    return {"ok": True, "cleared": solar_system_id}


async def sync_gate_bubble(
    from_system_id: int,
    to_system_id: int,
    *,
    side: str,
    note: str = "",
) -> dict[str, Any]:
    if not wanderer_sync_enabled():
        return {"skipped": True}

    custom_info = f"BUBBLE:{side}"
    if note:
        custom_info = f"{custom_info}:{note}"

    url = _api_url(f"/api/maps/{settings.wanderer_map_slug}/connections")
    params = {
        "solar_system_source": from_system_id,
        "solar_system_target": to_system_id,
    }
    try:
        async with httpx.AsyncClient(timeout=20.0) as client:
            resp = await client.patch(
                url,
                headers=_auth_headers(),
                params=params,
                json={"custom_info": custom_info},
            )
            resp.raise_for_status()
            return {"ok": True, "custom_info": custom_info}
    except Exception as exc:
        logger.exception("Wanderer gate bubble sync failed")
        return {"ok": False, "error": str(exc)}


async def sync_sov_label(solar_system_id: int, tag: str) -> dict[str, Any]:
    if not wanderer_sync_enabled():
        return {"skipped": True}

    existing = await _get_existing_labels(None, solar_system_id)
    labels = _merge_labels(existing, [tag])
    url = _api_url(f"/api/maps/{settings.wanderer_map_slug}/systems/{solar_system_id}")
    try:
        async with httpx.AsyncClient(timeout=20.0) as client:
            resp = await client.put(url, headers=_auth_headers(), json={"labels": labels})
            resp.raise_for_status()
            return {"ok": True}
    except Exception as exc:
        return {"ok": False, "error": str(exc)}


async def _maybe_db_ping(line: ParsedIntelLine) -> dict[str, Any]:
    """Optional: insert map_pings_v1 row (does not live-broadcast; API status is primary)."""
    if not settings.wanderer_db_ping_sync or not settings.wanderer_database_url:
        return {"skipped": True}

    eng = _wanderer_engine_instance()
    if eng is None:
        return {"skipped": True, "reason": "no wanderer DB URL"}

    char_eve_id = str(settings.wanderer_ping_character_eve_id or "")
    async with eng.begin() as conn:
        map_row = await conn.execute(
            text("SELECT id FROM maps_v1 WHERE slug = :slug LIMIT 1"),
            {"slug": settings.wanderer_map_slug},
        )
        map_id = map_row.scalar()
        if not map_id:
            return {"ok": False, "error": "map not found"}

        sys_row = await conn.execute(
            text(
                "SELECT id FROM map_system_v1 "
                "WHERE map_id = :map_id AND solar_system_id = :sid LIMIT 1"
            ),
            {"map_id": map_id, "sid": line.solar_system_id},
        )
        system_id = sys_row.scalar()
        if not system_id:
            return {"ok": False, "error": "system not on map"}

        char_id = None
        if char_eve_id:
            char_row = await conn.execute(
                text("SELECT id FROM character_v1 WHERE eve_id = :eve_id LIMIT 1"),
                {"eve_id": char_eve_id},
            )
            char_id = char_row.scalar()
        if not char_id:
            char_row = await conn.execute(
                text("SELECT id FROM character_v1 ORDER BY inserted_at LIMIT 1")
            )
            char_id = char_row.scalar()
        if not char_id:
            return {"ok": False, "error": "no wanderer character for ping"}

        await conn.execute(
            text(
                "INSERT INTO map_pings_v1 (map_id, system_id, character_id, type, message) "
                "VALUES (:map_id, :system_id, :character_id, 0, :message)"
            ),
            {
                "map_id": map_id,
                "system_id": system_id,
                "character_id": char_id,
                "message": _format_description(line),
            },
        )
    return {"ok": True, "db_ping": True}
