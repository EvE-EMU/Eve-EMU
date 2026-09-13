"""Global search across SDE types, systems, and tool registry."""

from __future__ import annotations

from sqlalchemy.ext.asyncio import AsyncSession

from app.services.route_planner import search_systems
from app.services.sde_search import search_types

TOOL_LINKS = [
    {"id": "buyback", "label": "Buyback", "href": "/commerce", "window": "buyback", "category": "Commerce"},
    {"id": "refine-calc", "label": "Refine vs Sell", "href": "/commerce", "window": "refine-calc", "category": "Commerce"},
    {"id": "appraisal", "label": "Appraisal", "href": "/commerce", "window": "appraisal", "category": "Commerce"},
    {"id": "market-browser", "label": "Market Browser", "href": "/commerce", "window": "market-browser", "category": "Commerce"},
    {"id": "ip-planner", "label": "Build Planner", "href": "https://eve-emu.com/industrial?tab=forge", "window": "ip-planner", "category": "Industrial Planning"},
    {"id": "ip-blueprints", "label": "Blueprints & Contracts", "href": "https://eve-emu.com/industrial/bp-copy", "window": "ip-blueprints", "category": "Industrial Planning"},
    {"id": "ip-projects", "label": "Project Costing", "href": "https://eve-emu.com/industrial?tab=projects", "window": "ip-projects", "category": "Industrial Planning"},
    {"id": "ip-storefront", "label": "Storefront", "href": "https://eve-emu.com/industrial?tab=market", "window": "ip-storefront", "category": "Industrial Planning"},
    {"id": "sde-browser", "label": "SDE Browser", "href": "/sde", "window": "sde-browser", "category": "SDE"},
    {"id": "map-visual", "label": "Route Map", "href": "/map", "window": "map-visual", "category": "Map"},
    {"id": "char-audit", "label": "Character Audit", "href": "/intelligence", "window": "char-audit", "category": "Intel"},
    {"id": "killboard", "label": "Killboard", "href": "/intelligence", "window": "killboard", "category": "Intel"},
]


async def global_search(session: AsyncSession, query: str, *, limit: int = 20) -> dict:
    q = (query or "").strip()
    if not q:
        return {"tools": TOOL_LINKS[:8], "types": [], "systems": []}

    q_lower = q.lower()
    tools = [t for t in TOOL_LINKS if q_lower in t["label"].lower() or q_lower in t["category"].lower()][:8]
    types = await search_types(session, q, limit=limit)
    systems = await search_systems(session, q, limit=min(limit, 12))
    return {"tools": tools, "types": types, "systems": systems}
