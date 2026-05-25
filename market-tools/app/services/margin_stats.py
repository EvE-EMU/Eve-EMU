"""Extra margin-finder metrics (history, order age, book depth)."""

from __future__ import annotations

from datetime import date, datetime, timedelta, timezone

from sqlalchemy import func, select

from app.db.models import MarketCatalogType, MarketHistoryDay, MarketOrder, MarketType
from app.db.session import session_scope
from app.services.market_history import resolve_hub_region_id


def _pct_change(current: float | None, previous: float | None) -> float | None:
    if current is None or previous is None or previous <= 0:
        return None
    return round(100 * (current - previous) / previous, 1)


async def enrich_margin_stats(rows: list[dict], *, location_id: int) -> None:
    """Attach Adam4EVE-style columns in place."""
    if not rows:
        return

    type_ids = [int(r["type_id"]) for r in rows]
    region_id = await resolve_hub_region_id()
    today = date.today()
    since_7 = today - timedelta(days=7)
    since_14 = today - timedelta(days=14)

    async with session_scope() as session:
        group_rows = (
            await session.execute(
                select(MarketType.type_id, MarketType.market_group_id).where(
                    MarketType.location_id == location_id,
                    MarketType.type_id.in_(type_ids),
                )
            )
        ).all()
        catalog_groups = (
            await session.execute(
                select(
                    MarketCatalogType.type_id,
                    MarketCatalogType.market_group_id,
                ).where(MarketCatalogType.type_id.in_(type_ids))
            )
        ).all()

        age_rows = (
            await session.execute(
                select(
                    MarketOrder.type_id,
                    MarketOrder.is_buy,
                    func.min(MarketOrder.issued).label("oldest"),
                    func.max(MarketOrder.synced_at).label("synced"),
                )
                .where(
                    MarketOrder.location_id == location_id,
                    MarketOrder.type_id.in_(type_ids),
                )
                .group_by(MarketOrder.type_id, MarketOrder.is_buy)
            )
        ).all()

        hist_rows = (
            await session.execute(
                select(MarketHistoryDay)
                .where(
                    MarketHistoryDay.region_id == region_id,
                    MarketHistoryDay.type_id.in_(type_ids),
                    MarketHistoryDay.day >= since_14,
                )
                .order_by(MarketHistoryDay.type_id, MarketHistoryDay.day)
            )
        ).scalars().all()

    group_by_type: dict[int, int | None] = {
        int(r.type_id): int(r.market_group_id) if r.market_group_id else None
        for r in group_rows
    }
    for r in catalog_groups:
        tid = int(r.type_id)
        if tid not in group_by_type or group_by_type[tid] is None:
            group_by_type[tid] = int(r.market_group_id) if r.market_group_id else None

    age_by_type: dict[int, dict] = {}
    now = datetime.now(timezone.utc)
    for r in age_rows:
        tid = int(r.type_id)
        slot = age_by_type.setdefault(tid, {"buy": None, "sell": None})
        issued = r.oldest
        if issued is None:
            continue
        if issued.tzinfo is None:
            issued = issued.replace(tzinfo=timezone.utc)
        hours = max(0.0, (now - issued).total_seconds() / 3600.0)
        key = "buy" if r.is_buy else "sell"
        prev = slot.get(key)
        if prev is None or hours > prev:
            slot[key] = round(hours, 1)

    hist_by_type: dict[int, list[MarketHistoryDay]] = {}
    for h in hist_rows:
        hist_by_type.setdefault(int(h.type_id), []).append(h)

    for row in rows:
        tid = int(row["type_id"])
        row["market_group_id"] = group_by_type.get(tid)
        buy_p = float(row.get("buy_price") or 0)
        sell_p = float(row.get("sell_price") or 0)
        buy_vol = int(row.get("buy_volume") or 0)
        sell_vol = int(row.get("sell_volume") or 0)
        buy_ord = int(row.get("buy_orders") or 0)
        sell_ord = int(row.get("sell_orders") or 0)

        row["avg_trades"] = buy_ord + sell_ord
        row["avg_isk_traded"] = round(
            (buy_p * buy_vol + sell_p * sell_vol) / max(buy_ord + sell_ord, 1), 0
        )
        row["s2b_volume"] = buy_vol
        row["s2b_num"] = buy_ord
        row["bfs_volume"] = sell_vol
        row["bfs_num"] = sell_ord

        ages = age_by_type.get(tid, {})
        buy_age = ages.get("buy")
        sell_age = ages.get("sell")
        if buy_age is not None and sell_age is not None:
            row["order_age_hours"] = min(buy_age, sell_age)
        else:
            row["order_age_hours"] = buy_age if buy_age is not None else sell_age

        days = hist_by_type.get(tid, [])
        recent = [d for d in days if d.day >= since_7]
        older = [d for d in days if d.day < since_7]

        if recent:
            avg_oc = sum(int(d.order_count or 0) for d in recent) / len(recent)
            avg_isk = sum(
                int(d.volume or 0) * float(d.average or 0) for d in recent
            ) / len(recent)
            row["avg_trades"] = round(avg_oc, 1)
            row["avg_isk_traded"] = round(avg_isk, 0)

            old_avg = (
                sum(float(d.average or 0) for d in older) / len(older) if older else None
            )
            new_avg = sum(float(d.average or 0) for d in recent) / len(recent)
            row["d7_buy_pct"] = _pct_change(buy_p, old_avg)
            row["d7_sell_pct"] = _pct_change(sell_p, new_avg if new_avg else old_avg)

            old_vol = sum(int(d.volume or 0) for d in older)
            new_vol = sum(int(d.volume or 0) for d in recent)
            row["d7_buy_vol_pct"] = _pct_change(float(buy_vol), float(old_vol) if old_vol else None)
            row["d7_sell_vol_pct"] = _pct_change(float(sell_vol), float(new_vol) if new_vol else None)
        else:
            row.setdefault("d7_buy_pct", None)
            row.setdefault("d7_sell_pct", None)
            row.setdefault("d7_buy_vol_pct", None)
            row.setdefault("d7_sell_vol_pct", None)
