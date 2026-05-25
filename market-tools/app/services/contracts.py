"""Sync and margin analysis for WOMP corporation contracts (ESI)."""

from __future__ import annotations

import asyncio
import logging
from datetime import UTC, datetime

from sqlalchemy import delete, select

from app.config import settings
from app.db.models import MarketContract, MarketContractItem
from app.db.session import session_scope
from app.esi.client import esi_get_paged_list
from app.services.catalog import catalog_type_name
from app.services.hub_prices import enrich_rows_with_hubs
from app.services.import_prices import schedule_import_price_sync

logger = logging.getLogger(__name__)

_contract_task: asyncio.Task | None = None

_ACTIVE = frozenset({"outstanding", "in_progress"})
_ITEM_TYPES = frozenset({"item_exchange", "auction"})


def contract_sync_running() -> bool:
    return _contract_task is not None and not _contract_task.done()


def issuer_corp_ids() -> list[int]:
    ids: list[int] = []
    if settings.womp_contract_issuer_corp_id:
        ids.append(int(settings.womp_contract_issuer_corp_id))
    raw = (settings.womp_contract_issuer_corp_ids or "").strip()
    for part in raw.split(","):
        part = part.strip()
        if part.isdigit():
            ids.append(int(part))
    return list(dict.fromkeys(ids))


def _parse_dt(raw: str | None) -> datetime | None:
    if not raw:
        return None
    try:
        return datetime.fromisoformat(raw.replace("Z", "+00:00"))
    except ValueError:
        return None


async def _fetch_corp_contracts(corp_id: int) -> list[dict]:
    pages = await esi_get_paged_list(
        f"/corporations/{corp_id}/contracts/",
        max_pages=30,
        auth=True,
    )
    return [p for p in pages if isinstance(p, dict)]


async def _fetch_contract_items(corp_id: int, contract_id: int) -> list[dict]:
    pages = await esi_get_paged_list(
        f"/corporations/{corp_id}/contracts/{contract_id}/items/",
        max_pages=5,
        auth=True,
    )
    return [p for p in pages if isinstance(p, dict)]


async def sync_corporation_contracts(*, issuer_corp_id: int) -> dict[str, int]:
    if not settings.esi_configured():
        return {"issuer_corp_id": issuer_corp_id, "contracts": 0, "items": 0, "error": "esi"}

    raw = await _fetch_corp_contracts(issuer_corp_id)
    now = datetime.now(UTC)
    contracts: list[MarketContract] = []
    items: list[MarketContractItem] = []

    for c in raw:
        ctype = str(c.get("type") or "")
        status = str(c.get("status") or "")
        if ctype not in _ITEM_TYPES or status not in _ACTIVE:
            continue
        try:
            cid = int(c["contract_id"])
            price = float(c.get("price") or 0)
        except (KeyError, TypeError, ValueError):
            continue
        contracts.append(
            MarketContract(
                contract_id=cid,
                issuer_corp_id=issuer_corp_id,
                contract_type=ctype,
                status=status,
                availability=str(c.get("availability") or ""),
                title=str(c.get("title") or "")[:512],
                price=price,
                date_issued=_parse_dt(c.get("date_issued")),
                date_expired=_parse_dt(c.get("date_expired")),
                synced_at=now,
            )
        )
        contract_items = await _fetch_contract_items(issuer_corp_id, cid)
        for it in contract_items:
            try:
                tid = int(it["type_id"])
                qty = int(it.get("quantity") or 1)
            except (KeyError, TypeError, ValueError):
                continue
            items.append(
                MarketContractItem(
                    contract_id=cid,
                    type_id=tid,
                    quantity=max(1, qty),
                    is_blueprint_copy=bool(it.get("is_blueprint_copy")),
                    me=int(it.get("material_efficiency") or 0),
                    te=int(it.get("time_efficiency") or 0),
                )
            )

    async with session_scope() as session:
        old_ids = (
            await session.execute(
                select(MarketContract.contract_id).where(
                    MarketContract.issuer_corp_id == issuer_corp_id
                )
            )
        ).scalars().all()
        if old_ids:
            await session.execute(
                delete(MarketContractItem).where(
                    MarketContractItem.contract_id.in_(old_ids)
                )
            )
        await session.execute(
            delete(MarketContract).where(
                MarketContract.issuer_corp_id == issuer_corp_id
            )
        )
        if contracts:
            session.add_all(contracts)
        if items:
            session.add_all(items)

    type_ids = {it.type_id for it in items}
    logger.info(
        "contracts corp %s: %s contracts, %s item lines, %s types",
        issuer_corp_id,
        len(contracts),
        len(items),
        len(type_ids),
    )
    return {
        "issuer_corp_id": issuer_corp_id,
        "contracts": len(contracts),
        "items": len(items),
        "types": len(type_ids),
    }


async def sync_all_contracts() -> dict[str, int]:
    corps = issuer_corp_ids()
    if not corps:
        return {"contracts": 0, "items": 0, "error": "no_issuer_corp_ids"}
    totals = {"contracts": 0, "items": 0}
    for corp_id in corps:
        stats = await sync_corporation_contracts(issuer_corp_id=corp_id)
        totals["contracts"] += stats.get("contracts", 0)
        totals["items"] += stats.get("items", 0)
    async with session_scope() as session:
        tids = (
            await session.execute(select(MarketContractItem.type_id).distinct())
        ).scalars().all()
    type_ids = [int(t) for t in tids]
    if type_ids and settings.wompstar_structure_id:
        schedule_import_price_sync(int(settings.wompstar_structure_id))
    return {
        "issuer_corps": corps,
        "contracts": totals["contracts"],
        "items": totals["items"],
        "types": len(type_ids),
    }


async def contract_margin_rows(*, location_id: int, limit: int = 500) -> list[dict]:
    """Per contract line: hub sells + margin vs contract unit price."""
    async with session_scope() as session:
        rows = (
            await session.execute(
                select(
                    MarketContractItem,
                    MarketContract,
                )
                .join(
                    MarketContract,
                    MarketContract.contract_id == MarketContractItem.contract_id,
                )
                .where(MarketContract.status.in_(_ACTIVE))
                .order_by(MarketContract.date_issued.desc())
                .limit(limit * 3)
            )
        ).all()

    out: list[dict] = []
    seen: set[tuple[int, int]] = set()
    for item, contract in rows:
        key = (int(contract.contract_id), int(item.type_id))
        if key in seen:
            continue
        seen.add(key)
        qty = max(1, int(item.quantity or 1))
        total = float(contract.price or 0)
        unit = total / qty if qty else total
        tid = int(item.type_id)
        name = await catalog_type_name(tid) or f"Type {tid}"
        out.append(
            {
                "contract_id": int(contract.contract_id),
                "type_id": tid,
                "type_name": name,
                "contract_type": contract.contract_type,
                "contract_status": contract.status,
                "contract_title": contract.title,
                "quantity": qty,
                "contract_total_isk": total,
                "contract_unit_isk": round(unit, 2),
                "me": item.me,
                "te": item.te,
                "is_bpc": item.is_blueprint_copy,
            }
        )
        if len(out) >= limit:
            break

    await enrich_rows_with_hubs(out)
    for row in out:
        unit = row.get("contract_unit_isk")
        womp = row.get("wompstar_sell")
        jita = row.get("jita_sell")
        amarr = row.get("amarr_sell")
        row["margin_vs_wompstar"] = (
            round(womp - unit, 2) if womp is not None and unit is not None else None
        )
        row["margin_vs_jita"] = (
            round(jita - unit, 2) if jita is not None and unit is not None else None
        )
        row["margin_vs_amarr"] = (
            round(amarr - unit, 2) if amarr is not None and unit is not None else None
        )
        row["pct_vs_wompstar"] = (
            round(100 * (womp - unit) / unit, 1)
            if womp is not None and unit and unit > 0
            else None
        )

    out.sort(
        key=lambda r: abs(r.get("margin_vs_wompstar") or 0),
        reverse=True,
    )
    return out


async def contract_trend_rows(*, limit: int = 200) -> list[dict]:
    """Alliance corp contracts: description, contents, price and volume trends."""
    corp_ids = issuer_corp_ids()
    if not corp_ids:
        return []

    async with session_scope() as session:
        rows = (
            await session.execute(
                select(MarketContractItem, MarketContract)
                .join(
                    MarketContract,
                    MarketContract.contract_id == MarketContractItem.contract_id,
                )
                .where(
                    MarketContract.status.in_(_ACTIVE),
                    MarketContract.issuer_corp_id.in_(corp_ids),
                    MarketContract.contract_type.in_(_ITEM_TYPES),
                )
                .order_by(MarketContract.date_issued.desc())
                .limit(limit * 5)
            )
        ).all()

    by_contract: dict[int, dict] = {}
    for item, contract in rows:
        cid = int(contract.contract_id)
        slot = by_contract.get(cid)
        if not slot:
            slot = {
                "contract_id": cid,
                "issuer_corp_id": int(contract.issuer_corp_id),
                "contract_type": contract.contract_type,
                "status": contract.status,
                "title": (contract.title or "").strip(),
                "description": (contract.title or "").strip(),
                "total_isk": float(contract.price or 0),
                "date_issued": contract.date_issued.isoformat()
                if contract.date_issued
                else None,
                "date_expired": contract.date_expired.isoformat()
                if contract.date_expired
                else None,
                "items": [],
                "quantity_total": 0,
            }
            by_contract[cid] = slot
        tid = int(item.type_id)
        qty = int(item.quantity or 1)
        name = await catalog_type_name(tid) or f"Type {tid}"
        slot["items"].append(
            {
                "type_id": tid,
                "type_name": name,
                "quantity": qty,
                "me": item.me,
                "te": item.te,
                "is_bpc": item.is_blueprint_copy,
            }
        )
        slot["quantity_total"] += qty

    out: list[dict] = []
    for slot in by_contract.values():
        qty = max(1, slot["quantity_total"])
        total = slot["total_isk"]
        slot["unit_isk"] = round(total / qty, 2) if qty else total
        parts = []
        for it in slot["items"][:8]:
            label = it["type_name"]
            if it.get("is_bpc"):
                label += f" BPC ME{it['me']} TE{it['te']}"
            parts.append(f"{label} ×{it['quantity']:,}")
        slot["contents"] = ", ".join(parts)
        if len(slot["items"]) > 8:
            slot["contents"] += f" (+{len(slot['items']) - 8} more)"
        slot["item_count"] = len(slot["items"])
        out.append(slot)

    out.sort(key=lambda r: r.get("date_issued") or "", reverse=True)
    return out[:limit]


async def _run_contract_sync() -> None:
    global _contract_task
    try:
        await sync_all_contracts()
    except Exception:
        logger.exception("contract sync failed")
    finally:
        _contract_task = None


def schedule_contract_sync() -> None:
    global _contract_task
    if contract_sync_running():
        return
    _contract_task = asyncio.create_task(_run_contract_sync())
