"""Linked character skill levels for SDE requirement checks."""

from __future__ import annotations

import logging

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.character_skills import CharacterSkillLevel
from app.models import LinkedCharacter, SsoUser
from app.services.esi import bearer_token, esi_get

logger = logging.getLogger(__name__)

_esi_cache: dict[int, dict[int, int]] = {}


async def _fetch_esi_character_skills(character_id: int, session: AsyncSession) -> dict[int, int]:
    if character_id in _esi_cache:
        return _esi_cache[character_id]
    token = await bearer_token(session, character_id=character_id)
    if not token:
        return {}
    status, body = await esi_get(
        f"/characters/{character_id}/skills/",
        auth=True,
        session=session,
        character_id=character_id,
    )
    if status != 200 or not isinstance(body, dict):
        return {}
    out: dict[int, int] = {}
    for row in body.get("skills") or []:
        if not isinstance(row, dict):
            continue
        sid = int(row.get("skill_id") or 0)
        lvl = int(row.get("trained_skill_level") or 0)
        if sid > 0:
            out[sid] = max(out.get(sid, 0), lvl)
    _esi_cache[character_id] = out
    return out


async def list_roster_characters(session: AsyncSession) -> list[dict]:
    roster: list[dict] = []
    user = await session.scalar(select(SsoUser).limit(1))
    if user:
        roster.append(
            {"character_id": user.character_id, "character_name": user.character_name, "is_main": True}
        )
        alts = (
            await session.scalars(
                select(LinkedCharacter).where(LinkedCharacter.owner_user_id == user.id)
            )
        ).all()
        for alt in alts:
            if alt.character_id == user.character_id:
                continue
            roster.append(
                {
                    "character_id": alt.character_id,
                    "character_name": alt.character_name,
                    "is_main": alt.is_main,
                }
            )
    if roster:
        return roster
    rows = await session.execute(
        select(CharacterSkillLevel.character_id, CharacterSkillLevel.character_name).distinct()
    )
    seen: set[int] = set()
    for cid, name in rows.all():
        if cid in seen:
            continue
        seen.add(cid)
        roster.append({"character_id": cid, "character_name": name, "is_main": len(seen) == 1})
    return roster


async def skills_for_character(session: AsyncSession, character_id: int) -> list[dict]:
    esi = await _fetch_esi_character_skills(character_id, session)
    if esi:
        return [{"skill_type_id": sid, "trained_level": lvl} for sid, lvl in sorted(esi.items())]
    rows = (
        await session.scalars(
            select(CharacterSkillLevel).where(CharacterSkillLevel.character_id == character_id)
        )
    ).all()
    return [
        {"skill_type_id": r.skill_type_id, "trained_level": r.trained_level, "skill_name": r.skill_name}
        for r in rows
    ]


async def get_character_skills_payload(session: AsyncSession) -> dict:
    roster = await list_roster_characters(session)
    characters: list[dict] = []
    best: dict[int, int] = {}
    for ch in roster:
        cid = int(ch["character_id"])
        skills = await skills_for_character(session, cid)
        for s in skills:
            sid = int(s["skill_type_id"])
            lvl = int(s["trained_level"])
            best[sid] = max(best.get(sid, 0), lvl)
        characters.append({**ch, "skills": skills})
    return {"characters": characters, "best_skills": best}


def characters_with_skill(characters: list[dict], skill_type_id: int, required_level: int) -> list[str]:
    names: list[str] = []
    for ch in characters:
        for s in ch.get("skills") or []:
            if int(s.get("skill_type_id") or 0) != skill_type_id:
                continue
            if int(s.get("trained_level") or 0) >= required_level:
                names.append(str(ch.get("character_name") or ch.get("character_id")))
                break
    return names
