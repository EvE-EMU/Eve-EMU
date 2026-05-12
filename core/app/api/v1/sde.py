"""SDE read API — types, groups, solar systems (Postgres; import from Fuzzwork SQLite)."""

from __future__ import annotations

from fastapi import APIRouter, HTTPException, Query

from app.config import settings
from app.sde import repository as sde_repo
from app.sde.schemas import SdeInvGroupOut, SdeSolarSystemOut, SdeStatusOut, SdeTypeOut

router = APIRouter(prefix="/sde", tags=["SDE"])


def _require_db() -> None:
    if not settings.database_url:
        raise HTTPException(
            status_code=503,
            detail="CORE_DATABASE_URL is not set; SDE API is unavailable.",
        )


@router.get("/status", response_model=SdeStatusOut)
async def sde_status() -> SdeStatusOut:
    return await sde_repo.sde_status()


@router.get("/types/{type_id}", response_model=SdeTypeOut)
async def get_type(type_id: int) -> SdeTypeOut:
    _require_db()
    row = await sde_repo.get_type_by_id(type_id)
    if row is None:
        raise HTTPException(status_code=404, detail="Type not found")
    return row


@router.get("/types", response_model=list[SdeTypeOut])
async def search_types(
    q: str = Query(..., min_length=2, max_length=200, description="Substring search on type name"),
    limit: int = Query(50, ge=1, le=200),
) -> list[SdeTypeOut]:
    _require_db()
    return await sde_repo.search_types(q=q, limit=limit)


@router.get("/groups/{group_id}/types", response_model=list[SdeTypeOut])
async def list_types_in_group(
    group_id: int,
    limit: int = Query(200, ge=1, le=1000),
) -> list[SdeTypeOut]:
    _require_db()
    return await sde_repo.list_types_for_group(group_id=group_id, limit=limit)


@router.get("/groups/{group_id}", response_model=SdeInvGroupOut)
async def get_group(group_id: int) -> SdeInvGroupOut:
    _require_db()
    row = await sde_repo.get_group_by_id(group_id)
    if row is None:
        raise HTTPException(status_code=404, detail="Group not found")
    return row


@router.get("/systems/by-name/{name}", response_model=SdeSolarSystemOut)
async def get_system_by_name(name: str) -> SdeSolarSystemOut:
    _require_db()
    row = await sde_repo.get_solar_system_by_name(name=name)
    if row is None:
        raise HTTPException(status_code=404, detail="Solar system not found")
    return row


@router.get("/systems/{solar_system_id}", response_model=SdeSolarSystemOut)
async def get_system(solar_system_id: int) -> SdeSolarSystemOut:
    _require_db()
    row = await sde_repo.get_solar_system_by_id(solar_system_id)
    if row is None:
        raise HTTPException(status_code=404, detail="Solar system not found")
    return row


@router.get("/systems", response_model=list[SdeSolarSystemOut])
async def search_systems(
    q: str = Query(..., min_length=2, max_length=200, description="Substring search on system name"),
    limit: int = Query(50, ge=1, le=200),
) -> list[SdeSolarSystemOut]:
    _require_db()
    return await sde_repo.search_solar_systems(q=q, limit=limit)
