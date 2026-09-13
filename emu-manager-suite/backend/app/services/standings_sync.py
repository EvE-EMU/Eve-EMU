"""ESI character standings sync and board."""

from __future__ import annotations

import logging
from datetime import UTC, datetime
from typing import Any

import httpx
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import settings
from app.models.onboarding import CharacterStanding
from app.models.tools import SsoUser
from app.services.audit_scopes import parse_granted_scopes
from app.services.esi import bearer_token

logger = logging.getLogger(__name__)
_ESI = (settings.esi_base_url or "https://esi.evetech.net/latest").rstrip("/")
_UA = "EVE-EMU-EMUMS/1.0 (+https://emums.eve-emu.com; standings)"
STANDINGS_SCOPE = "esi-characters.read_standings.v1"


async def sync_character_standings(session: AsyncSession, character_id: int) -> dict[str, Any]:
    user = await session.scalar(select(SsoUser).where(SsoUser.character_id == character_id))
    if not user:
        return {"error": "not_authenticated", "count": 0}
    scopes = parse_granted_scopes(user.scopes_json)
    if STANDINGS_SCOPE not in scopes:
        return {"error": "missing_scope", "message": "Need esi-characters.read_standings.v1", "count": 0}

    token = await bearer_token(session, character_id=character_id)
    if not token:
        return {"error": "no_token", "count": 0}

    headers = {"Authorization": f"Bearer {token}", "User-Agent": _UA}
    async with httpx.AsyncClient(timeout=30.0) as client:
        resp = await client.get(f"{_ESI}/characters/{character_id}/standings/", headers=headers)
        if resp.status_code != 200:
            return {"error": f"esi_{resp.status_code}", "count": 0}
        rows = resp.json()
    if not isinstance(rows, list):
        return {"error": "bad_payload", "count": 0}

    # Resolve names for from_ids
    ids = [int(r.get("from_id") or 0) for r in rows if isinstance(r, dict)]
    name_map: dict[int, str] = {}
    for offset in range(0, len(ids), 1000):
        chunk = [i for i in ids[offset : offset + 1000] if i > 0]
        if not chunk:
            continue
        async with httpx.AsyncClient(timeout=30.0) as client:
            named = await client.post(
                f"{_ESI}/universe/names/",
                json=chunk,
                headers={"User-Agent": _UA, "Content-Type": "application/json"},
            )
            if named.status_code == 200 and isinstance(named.json(), list):
                for entry in named.json():
                    if isinstance(entry, dict) and entry.get("id"):
                        name_map[int(entry["id"])] = str(entry.get("name") or "")

    # Replace standings for this character
    existing = (
        await session.scalars(select(CharacterStanding).where(CharacterStanding.character_id == character_id))
    ).all()
    for row in existing:
        await session.delete(row)
    await session.flush()

    now = datetime.now(UTC)
    count = 0
    for row in rows:
        if not isinstance(row, dict):
            continue
        from_id = int(row.get("from_id") or 0)
        if from_id <= 0:
            continue
        session.add(
            CharacterStanding(
                character_id=character_id,
                from_id=from_id,
                from_type=str(row.get("from_type") or "character"),
                from_name=name_map.get(from_id, ""),
                standing=float(row.get("standing") or 0),
                synced_at=now,
            )
        )
        count += 1
    await session.flush()
    return {"count": count, "character_id": character_id, "synced_at": now.isoformat()}


async def standings_board(session: AsyncSession, character_id: int) -> dict[str, Any]:
    rows = (
        await session.scalars(
            select(CharacterStanding)
            .where(CharacterStanding.character_id == character_id)
            .order_by(CharacterStanding.standing.desc())
        )
    ).all()
    contacts = [
        {
            "from_id": int(r.from_id),
            "from_type": r.from_type,
            "from_name": r.from_name or f"ID {r.from_id}",
            "standing": float(r.standing),
            "synced_at": r.synced_at.isoformat() if r.synced_at else None,
        }
        for r in rows
    ]
    positives = [c for c in contacts if c["standing"] > 0]
    negatives = [c for c in contacts if c["standing"] < 0]
    return {
        "character_id": character_id,
        "count": len(contacts),
        "positive_count": len(positives),
        "negative_count": len(negatives),
        "contacts": contacts,
        "top_allies": positives[:15],
        "top_hostiles": sorted(negatives, key=lambda c: c["standing"])[:15],
    }
