"""Import hub (Jita, Amarr) best bid/ask for types listed at WOMPSTAR."""

from __future__ import annotations

import asyncio
import logging
from datetime import UTC, datetime

from sqlalchemy import select

from app.config import settings
from app.db.models import SyncRun, TypeAppraisal
from app.db.session import session_scope
from app.esi.client import esi_get_paged_list

logger = logging.getLogger(__name__)

_import_task: asyncio.Task | None = None


def import_sync_running() -> bool:
    return _import_task is not None and not _import_task.done()


async def _best_prices_for_type(*, region_id: int, type_id: int) -> tuple[float | None, float | None]:
    """Min sell and max buy in a region for one type (public ESI)."""
    orders = await esi_get_paged_list(
        f"/markets/{region_id}/orders/",
        params={"type_id": type_id},
        max_pages=5,
        auth=False,
    )
    best_sell: float | None = None
    best_buy: float | None = None
    for o in orders:
        if not isinstance(o, dict):
            continue
        try:
            price = float(o["price"])
        except (KeyError, TypeError, ValueError):
            continue
        if o.get("is_buy_order"):
            if best_buy is None or price > best_buy:
                best_buy = price
        else:
            if best_sell is None or price < best_sell:
                best_sell = price
    return best_sell, best_buy


async def sync_import_prices_for_types(
    type_ids: list[int],
    *,
    wompstar_prices: dict[int, tuple[float | None, float | None]] | None = None,
) -> int:
    """Fetch Jita + Amarr orders per type and upsert type_appraisals."""
    if not type_ids:
        return 0
    jita_rid = int(settings.default_import_region_id)
    amarr_rid = int(settings.default_amarr_region_id)
    sem = asyncio.Semaphore(max(2, settings.esi_max_concurrent))
    updated = 0
    now = datetime.now(UTC)

    async def _one(tid: int) -> TypeAppraisal | None:
        async with sem:
            jita_sell, jita_buy = await _best_prices_for_type(region_id=jita_rid, type_id=tid)
            amarr_sell, amarr_buy = await _best_prices_for_type(region_id=amarr_rid, type_id=tid)
        if (
            jita_sell is None
            and jita_buy is None
            and amarr_sell is None
            and amarr_buy is None
        ):
            return None
        womp = (wompstar_prices or {}).get(tid, (None, None))
        return TypeAppraisal(
            type_id=tid,
            wompstar_sell=womp[0],
            wompstar_buy=womp[1],
            jita_sell=jita_sell,
            jita_buy=jita_buy,
            amarr_sell=amarr_sell,
            amarr_buy=amarr_buy,
            updated_at=now,
        )

    rows = await asyncio.gather(*[_one(tid) for tid in type_ids])
    to_save = [r for r in rows if r is not None]
    if not to_save:
        return 0

    async with session_scope() as session:
        for row in to_save:
            existing = await session.scalar(
                select(TypeAppraisal).where(TypeAppraisal.type_id == row.type_id).limit(1)
            )
            if existing:
                existing.jita_sell = row.jita_sell
                existing.jita_buy = row.jita_buy
                existing.amarr_sell = row.amarr_sell
                existing.amarr_buy = row.amarr_buy
                existing.wompstar_sell = row.wompstar_sell
                existing.wompstar_buy = row.wompstar_buy
                existing.updated_at = now
            else:
                session.add(row)
        updated = len(to_save)

    return updated


async def sync_import_prices_for_hub(
    *,
    location_id: int,
) -> dict[str, int]:
    """Sync Jita + Amarr prices for all types listed at the structure hub."""
    from app.services.browser import listed_types_catalog

    started = datetime.now(UTC)
    catalog = await listed_types_catalog(location_id=location_id)
    types = catalog.get("types") or []
    if not types:
        return {"location_id": location_id, "types": 0, "updated": 0}

    womp = {
        int(t["type_id"]): (t.get("best_sell"), t.get("best_buy"))
        for t in types
    }
    type_ids = list(womp.keys())
    updated = await sync_import_prices_for_types(type_ids, wompstar_prices=womp)

    async with session_scope() as session:
        session.add(
            SyncRun(
                job="import_prices",
                started_at=started,
                finished_at=datetime.now(UTC),
                ok=True,
                detail=f"types={len(type_ids)} updated={updated}",
            )
        )

    return {
        "location_id": location_id,
        "jita_region_id": int(settings.default_import_region_id),
        "amarr_region_id": int(settings.default_amarr_region_id),
        "types": len(type_ids),
        "updated": updated,
    }


async def _run_import_job(location_id: int) -> None:
    global _import_task
    try:
        stats = await sync_import_prices_for_hub(location_id=location_id)
        logger.info("import price sync ok: %s", stats)
    except Exception:
        logger.exception("import price sync failed")
    finally:
        _import_task = None


def schedule_import_price_sync(location_id: int) -> None:
    """Background Jita/Amarr price sync (non-blocking)."""
    global _import_task
    if import_sync_running():
        return
    _import_task = asyncio.create_task(_run_import_job(location_id))
