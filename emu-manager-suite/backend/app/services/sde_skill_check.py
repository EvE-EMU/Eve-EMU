"""Skill requirement extraction and ownership checks."""

from __future__ import annotations

from sqlalchemy.ext.asyncio import AsyncSession

from app.services.sde_type_detail import get_skill_requirements_for_type

_req_cache: dict[int, list[dict]] = {}


async def requirements_for_type(session: AsyncSession, type_id: int) -> list[dict]:
    if type_id in _req_cache:
        return _req_cache[type_id]
    reqs = await get_skill_requirements_for_type(session, type_id)
    _req_cache[type_id] = reqs
    return reqs


def check_requirements(requirements: list[dict], best_skills: dict[int, int]) -> dict:
    missing: list[dict] = []
    for req in requirements:
        sid = int(req.get("type_id") or 0)
        need = int(req.get("level") or 1)
        have = int(best_skills.get(sid) or 0)
        if have < need:
            missing.append(
                {
                    "type_id": sid,
                    "name": req.get("name") or f"Skill {sid}",
                    "required_level": need,
                    "trained_level": have,
                }
            )
    return {"can_use": len(missing) == 0, "missing": missing, "requirements": requirements}


async def skill_check_types(
    session: AsyncSession,
    type_ids: list[int],
    best_skills: dict[int, int],
) -> dict[int, dict]:
    out: dict[int, dict] = {}
    for tid in type_ids[:100]:
        reqs = await requirements_for_type(session, tid)
        out[tid] = check_requirements(reqs, best_skills)
    return out
