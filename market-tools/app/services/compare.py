"""Price compare: WOMPSTAR hub vs Janice (Jita / Amarr) appraisal prices."""

from __future__ import annotations

from sqlalchemy import select

from app.config import settings
from app.db.models import TypeAppraisal
from app.db.session import session_scope
from app.services.browser import listed_types_catalog
from app.services.import_prices import schedule_import_price_sync
from app.services.janice import janice_configured, janice_prices_by_type_id
from app.services.name_resolver import catalog_names, display_name, hub_names


async def price_compare(
    *,
    location_id: int,
    limit: int = 500,
    region_id: int | None = None,
) -> dict:
    catalog = await listed_types_catalog(location_id=location_id)
    types = (catalog.get("types") or [])[:limit]
    type_ids = [int(t["type_id"]) for t in types]

    jita_janice: dict[int, dict] = {}
    amarr_janice: dict[int, dict] = {}
    use_janice = janice_configured()
    if use_janice and type_ids:
        jita_janice = await janice_prices_by_type_id(type_ids, market="jita")
        amarr_janice = await janice_prices_by_type_id(type_ids, market="amarr")

    appraisals: dict[int, TypeAppraisal] = {}
    if type_ids and not use_janice:
        async with session_scope() as session:
            rows = (
                await session.execute(
                    select(TypeAppraisal).where(TypeAppraisal.type_id.in_(type_ids))
                )
            ).scalars().all()
            appraisals = {int(a.type_id): a for a in rows}

    missing = 0
    if not use_janice:
        def _missing(appr: TypeAppraisal | None, sell_attr: str, buy_attr: str) -> bool:
            if not appr:
                return True
            return getattr(appr, sell_attr) is None and getattr(appr, buy_attr) is None

        missing = sum(
            1
            for tid in type_ids
            if _missing(appraisals.get(tid), "jita_sell", "jita_buy")
            or _missing(appraisals.get(tid), "amarr_sell", "amarr_buy")
        )
        if type_ids and missing > len(type_ids) * 0.2:
            schedule_import_price_sync(location_id)

    cat_names = await catalog_names(type_ids)
    hub_name_map = await hub_names(location_id, type_ids)

    rid = int(region_id or settings.default_import_region_id)
    rows = []
    for t in types:
        tid = int(t["type_id"])
        appr = appraisals.get(tid)
        jj = jita_janice.get(tid)
        aj = amarr_janice.get(tid)
        label = display_name(tid, t.get("name") or hub_name_map.get(tid), cat_names.get(tid))

        if jj:
            jita_sell = jj.get("sell")
            jita_buy = jj.get("buy")
        else:
            jita_sell = appr.jita_sell if appr else None
            jita_buy = appr.jita_buy if appr else None

        if aj:
            amarr_sell = aj.get("sell")
            amarr_buy = aj.get("buy")
        else:
            amarr_sell = appr.amarr_sell if appr else None
            amarr_buy = appr.amarr_buy if appr else None

        rows.append(
            {
                "type_id": tid,
                "name": label,
                "type_name": label,
                "best_sell": t.get("best_sell"),
                "best_buy": t.get("best_buy"),
                "jita_sell": jita_sell,
                "jita_buy": jita_buy,
                "amarr_sell": amarr_sell,
                "amarr_buy": amarr_buy,
            }
        )
    rows.sort(key=lambda r: (r["name"] or "").lower())

    return {
        "location_id": location_id,
        "import_region_id": rid,
        "import_station_id": settings.default_import_station_id,
        "import_label": "Jita 4-4 (Janice)" if use_janice else "Jita 4-4 (The Forge)",
        "amarr_region_id": settings.default_amarr_region_id,
        "amarr_station_id": settings.default_amarr_station_id,
        "amarr_label": "Amarr VIII (Janice)" if use_janice else "Amarr VIII (Domain)",
        "janice_used": use_janice,
        "count": len(rows),
        "hub_prices_pending": missing > 0 and not use_janice,
        "jita_pending": missing > 0 and not use_janice,
        "types": rows,
    }
