"""Pull structure market orders into Postgres (WOMPSTAR)."""

from __future__ import annotations

import asyncio
import logging
from datetime import UTC, datetime

from sqlalchemy import delete

from app.config import settings
from app.db.models import MarketOrder, SyncRun
from app.db.session import session_scope
from app.esi.client import esi_get, esi_get_paged_list
from app.services.import_prices import schedule_import_price_sync
from app.services.market_groups import sync_listed_market_groups
from app.services.type_names import sync_listed_type_names

logger = logging.getLogger(__name__)

_groups_task: asyncio.Task | None = None


async def _sync_market_groups_background(location_id: int) -> None:
    global _groups_task
    try:
        count = await sync_listed_market_groups(location_id=location_id)
        logger.info("market groups sync ok: %d groups", count)
    except Exception:
        logger.exception("market groups sync failed")
    finally:
        _groups_task = None


def schedule_market_groups_sync(location_id: int) -> None:
    """Run slow ESI group lookups without blocking order/name sync."""
    global _groups_task
    if _groups_task and not _groups_task.done():
        return
    _groups_task = asyncio.create_task(_sync_market_groups_background(location_id))


def _parse_issued(raw: str | None) -> datetime | None:
    if not raw:
        return None
    try:
        return datetime.fromisoformat(raw.replace("Z", "+00:00"))
    except ValueError:
        return None


async def sync_wompstar_orders() -> dict[str, int]:
    sid = int(settings.wompstar_structure_id or 0)
    if not sid:
        return {"skipped": 1, "reason": "MARKET_WOMPSTAR_STRUCTURE_ID unset"}
    if not settings.esi_configured():
        return {
            "skipped": 1,
            "reason": "ESI not configured (AA token bridge or MARKET_ESI_REFRESH_TOKEN)",
        }

    started = datetime.now(UTC)
    rows: list[MarketOrder] = []

    path = f"/markets/structures/{sid}/"
    status, probe = await esi_get(path, params={"page": 1}, auth=True)
    if status == 401:
        logger.error("structure market sync: ESI 401 — refresh token invalid or missing scope")
        return {"structure_id": sid, "orders": 0, "error": "esi_401"}
    if status == 403:
        logger.error("structure market sync: ESI 403 — character cannot view this structure market")
        return {"structure_id": sid, "orders": 0, "error": "esi_403"}
    if status not in (200, 404):
        logger.error("structure market sync: ESI %s — %s", status, probe)
        return {"structure_id": sid, "orders": 0, "error": f"esi_{status}"}

    pages: list = []
    if status == 200:
        pages = await esi_get_paged_list(path, max_pages=50, auth=True)
    now = datetime.now(UTC)
    logger.info("structure %s: %d orders from ESI (status=%s)", sid, len(pages), status)
    for o in pages:
        if not isinstance(o, dict):
            continue
        try:
            order_id = int(o["order_id"])
            type_id = int(o["type_id"])
            price = float(o["price"])
            vol = int(o.get("volume_remain") or 0)
            vol_total = int(o.get("volume_total") or vol)
        except (KeyError, TypeError, ValueError):
            continue
        rows.append(
            MarketOrder(
                order_id=order_id,
                location_id=sid,
                type_id=type_id,
                is_buy=bool(o.get("is_buy_order")),
                price=price,
                volume_remain=vol,
                volume_total=vol_total,
                min_volume=int(o.get("min_volume") or 1),
                range=str(o.get("range") or "station"),
                issued=_parse_issued(o.get("issued")),
                duration=int(o.get("duration") or 0),
                synced_at=now,
            )
        )

    async with session_scope() as session:
        await session.execute(
            delete(MarketOrder).where(MarketOrder.location_id == sid)
        )
        if rows:
            session.add_all(rows)
        session.add(
            SyncRun(
                job="structure_orders",
                started_at=started,
                finished_at=datetime.now(UTC),
                ok=True,
                detail=f"orders={len(rows)}",
            )
        )

    type_count = await sync_listed_type_names(location_id=sid)
    schedule_market_groups_sync(sid)
    schedule_import_price_sync(sid)
    return {
        "structure_id": sid,
        "orders": len(rows),
        "types": type_count,
        "market_groups": "pending",
    }
