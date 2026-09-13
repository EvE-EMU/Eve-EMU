"""Sync corporation titles from ESI into the database."""

from __future__ import annotations

import logging
from datetime import UTC, datetime

from sqlalchemy import delete, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.tools import CharacterCorpTitle
from app.services.audit_scopes import parse_granted_scopes
from app.services.esi import esi_get

logger = logging.getLogger(__name__)

TITLES_SCOPE = "esi-characters.read_titles.v1"


async def sync_character_corp_titles(
    session: AsyncSession,
    *,
    character_id: int,
    corporation_id: int,
    scopes_json: str,
) -> list[dict]:
    granted = parse_granted_scopes(scopes_json)
    if TITLES_SCOPE not in granted:
        return []
    if corporation_id <= 0:
        return []

    status, body = await esi_get(
        f"/characters/{character_id}/titles/",
        auth=True,
        session=session,
        character_id=character_id,
    )
    if status != 200 or not isinstance(body, list):
        logger.warning("titles sync failed for %s: HTTP %s", character_id, status)
        return []

    now = datetime.now(UTC)
    await session.execute(
        delete(CharacterCorpTitle).where(CharacterCorpTitle.character_id == character_id)
    )
    out: list[dict] = []
    for row in body:
        if not isinstance(row, dict):
            continue
        title_id = int(row.get("title_id") or 0)
        if title_id <= 0:
            continue
        name = str(row.get("name") or f"Title {title_id}")
        session.add(
            CharacterCorpTitle(
                character_id=character_id,
                corporation_id=corporation_id,
                title_id=title_id,
                title_name=name,
                synced_at=now,
            )
        )
        out.append({"title_id": title_id, "title_name": name})
    return out
