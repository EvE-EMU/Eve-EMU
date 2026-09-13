"""Knowledge & SDE integration — unified wiki + database browser."""

from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.ext.asyncio import AsyncSession

from app.auth.deps import require_api_key
from app.db.session import get_db
from app.services.knowledge_bridge import (
    fetch_wiki_article,
    knowledge_search,
    unified_type_lookup,
    wiki_for_type,
)

router = APIRouter(prefix="/knowledge", tags=["Knowledge"], dependencies=[Depends(require_api_key)])


@router.get("/search")
async def search_knowledge(
    q: str = Query("", min_length=0),
    limit: int = Query(20, ge=1, le=50),
    scope: str = Query("all", pattern="^(all|sde|wiki)$"),
    wiki_category: str = Query(
        "all",
        pattern="^(all|guides|types|corporations|alliances|sde)$",
    ),
    db: AsyncSession = Depends(get_db),
) -> dict:
    return await knowledge_search(
        db, q, limit=limit, scope=scope, wiki_category=wiki_category
    )


@router.get("/wiki/page")
async def wiki_page(title: str = Query(..., min_length=1)) -> dict:
    article = await fetch_wiki_article(title)
    if not article:
        raise HTTPException(404, detail="Wiki page not found")
    return article


@router.get("/wiki/types/{type_id}")
async def wiki_type_page(type_id: int, db: AsyncSession = Depends(get_db)) -> dict:
    return await wiki_for_type(db, type_id)


@router.get("/types/{type_id}")
async def unified_type(
    type_id: int,
    include_skill_check: bool = Query(False),
    db: AsyncSession = Depends(get_db),
) -> dict:
    result = await unified_type_lookup(db, type_id, include_skill_check=include_skill_check)
    if not result.get("sde") and not result.get("wiki", {}).get("found"):
        raise HTTPException(404, detail="Type not found")
    return result
