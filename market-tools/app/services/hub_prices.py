"""Regional hub best bid/ask (Jita, Amarr, WOMPSTAR) for margin / contract views."""

from __future__ import annotations

from sqlalchemy import select

from app.config import settings
from app.db.models import TypeAppraisal
from app.db.session import session_scope
from app.services.janice import janice_configured, janice_prices_by_type_id


def _diff(a: float | None, b: float | None) -> float | None:
    if a is None or b is None:
        return None
    return round(a - b, 2)


async def load_appraisals(type_ids: list[int]) -> dict[int, TypeAppraisal]:
    if not type_ids:
        return {}
    async with session_scope() as session:
        rows = (
            await session.execute(
                select(TypeAppraisal).where(TypeAppraisal.type_id.in_(type_ids))
            )
        ).scalars().all()
    return {int(a.type_id): a for a in rows}


def attach_hub_prices(rows: list[dict], appraisals: dict[int, TypeAppraisal]) -> None:
    """Add jita/amarr/womp columns and cross-hub margins in place."""
    for row in rows:
        tid = int(row["type_id"])
        appr = appraisals.get(tid)
        womp_sell = row.get("sell_price") or row.get("wompstar_sell")
        womp_buy = row.get("buy_price") or row.get("wompstar_buy")
        if appr:
            womp_sell = womp_sell if womp_sell is not None else appr.wompstar_sell
            womp_buy = womp_buy if womp_buy is not None else appr.wompstar_buy
        jita_sell = appr.jita_sell if appr else None
        jita_buy = appr.jita_buy if appr else None
        amarr_sell = appr.amarr_sell if appr else None
        amarr_buy = appr.amarr_buy if appr else None

        row["wompstar_sell"] = womp_sell
        row["wompstar_buy"] = womp_buy
        row["jita_sell"] = jita_sell
        row["jita_buy"] = jita_buy
        row["amarr_sell"] = amarr_sell
        row["amarr_buy"] = amarr_buy
        row["margin_womp_vs_jita"] = _diff(womp_sell, jita_sell)
        row["margin_womp_vs_amarr"] = _diff(womp_sell, amarr_sell)
        row["margin_jita_vs_amarr"] = _diff(jita_sell, amarr_sell)


async def enrich_rows_with_hubs(rows: list[dict]) -> list[dict]:
    if not rows:
        return rows
    tids = [int(r["type_id"]) for r in rows]
    appraisals = await load_appraisals(tids)
    attach_hub_prices(rows, appraisals)
    if janice_configured():
        jita = await janice_prices_by_type_id(tids, market="jita")
        amarr = await janice_prices_by_type_id(tids, market="amarr")
        for row in rows:
            tid = int(row["type_id"])
            if tid in jita:
                row["jita_sell"] = jita[tid].get("sell")
                row["jita_buy"] = jita[tid].get("buy")
            if tid in amarr:
                row["amarr_sell"] = amarr[tid].get("sell")
                row["amarr_buy"] = amarr[tid].get("buy")
    return rows


def hub_labels() -> dict[str, str]:
    return {
        "jita": "Jita 4-4",
        "amarr": "Amarr VIII",
        "wompstar": settings.wompstar_structure_name or "WOMPSTAR",
    }
