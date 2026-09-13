"""Unified SDE + MediaWiki knowledge lookups."""

from __future__ import annotations

import asyncio
from typing import Any

from sqlalchemy.ext.asyncio import AsyncSession

from app.services import mediawiki
from app.services.sde_search import get_type
from app.services.sde_type_detail import get_type_detail
from app.services.wiki_content import (
    clean_snippet,
    extract_type_id,
    sanitize_wiki_html,
    wiki_category_from_title,
    wiki_title_for_type,
)


async def fetch_wiki_article(title: str) -> dict[str, Any] | None:
    parsed = await mediawiki.parse_page(title)
    if not parsed:
        return None

    sanitized = sanitize_wiki_html(parsed["html"])
    resolved_title = parsed["title"]
    if sanitized["is_redirect"] and sanitized["redirect_title"]:
        follow = await mediawiki.parse_page(sanitized["redirect_title"])
        if follow:
            sanitized = sanitize_wiki_html(follow["html"])
            resolved_title = follow["title"]
            parsed = follow

    return {
        "found": True,
        "title": resolved_title,
        "display_title": parsed.get("displaytitle") or resolved_title,
        "pageid": parsed.get("pageid"),
        "html": sanitized["html"],
        "type_id": sanitized["type_id"],
        "links": sanitized["links"],
        "sections": parsed.get("sections") or [],
        "external_url": mediawiki.wiki_page_url(resolved_title),
    }


async def wiki_for_type(db: AsyncSession, type_id: int) -> dict[str, Any]:
    row = await get_type(db, type_id)
    if not row:
        return {"found": False, "type_id": type_id}

    candidates = [
        wiki_title_for_type(type_id),
        f"SDE/Types/{row['name']}" if row.get("name") else "",
    ]
    for title in candidates:
        if not title:
            continue
        article = await fetch_wiki_article(title)
        if article:
            article["type_id"] = article.get("type_id") or type_id
            return article

    return {
        "found": False,
        "type_id": type_id,
        "title": wiki_title_for_type(type_id),
        "external_url": mediawiki.wiki_page_url(wiki_title_for_type(type_id)),
    }


async def unified_type_lookup(
    db: AsyncSession,
    type_id: int,
    *,
    include_skill_check: bool = False,
) -> dict[str, Any]:
    from app.services.sde_character_skills import get_character_skills_payload
    from app.services.sde_skill_check import check_requirements

    sde_task = get_type_detail(db, type_id)
    wiki_task = wiki_for_type(db, type_id)
    sde_row, wiki_row = await asyncio.gather(sde_task, wiki_task)

    if not sde_row:
        return {"type_id": type_id, "sde": None, "wiki": wiki_row}

    if include_skill_check:
        payload = await get_character_skills_payload(db)
        sde_row["skill_check"] = check_requirements(
            sde_row.get("requirements") or [], payload.get("best_skills") or {}
        )

    return {"type_id": type_id, "sde": sde_row, "wiki": wiki_row}


async def knowledge_search(
    db: AsyncSession,
    query: str,
    *,
    limit: int = 20,
    scope: str = "all",
    wiki_category: str = "all",
) -> dict[str, Any]:
    from app.services.sde_search import search_types

    sde_limit = min(limit, 30)
    wiki_limit = min(limit, 20)
    scope_norm = (scope or "all").lower()
    wiki_cat_norm = (wiki_category or "all").lower()
    include_sde = scope_norm in ("all", "sde")
    include_wiki = scope_norm in ("all", "wiki")

    sde_rows: list[Any] = []
    wiki_hits: list[Any] = []
    if query.strip():
        coros: list[Any] = []
        labels: list[str] = []
        if include_sde:
            coros.append(search_types(db, query, limit=sde_limit))
            labels.append("sde")
        if include_wiki:
            coros.append(mediawiki.search_pages(query, limit=wiki_limit))
            labels.append("wiki")
        if coros:
            for label, result in zip(labels, await asyncio.gather(*coros), strict=True):
                if label == "sde":
                    sde_rows = result
                else:
                    wiki_hits = result

    wiki = []
    for hit in wiki_hits:
        title = str(hit.get("title") or "")
        category = wiki_category_from_title(title)
        if wiki_cat_norm != "all" and category != wiki_cat_norm:
            continue
        snippet = clean_snippet(str(hit.get("snippet") or ""))
        wiki.append(
            {
                "title": title,
                "pageid": int(hit.get("pageid") or 0),
                "snippet": snippet,
                "type_id": extract_type_id(snippet, title),
                "category": category,
                "external_url": mediawiki.wiki_page_url(title),
            }
        )

    return {
        "query": query,
        "scope": scope_norm,
        "wiki_category": wiki_cat_norm,
        "sde": sde_rows if include_sde else [],
        "wiki": wiki if include_wiki else [],
    }
