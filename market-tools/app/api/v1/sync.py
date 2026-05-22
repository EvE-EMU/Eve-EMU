from fastapi import APIRouter

from app.config import settings
from app.services.contracts import contract_sync_running, schedule_contract_sync
from app.services.trade_volume import history_sync_running, schedule_history_sync
from app.services.import_prices import import_sync_running, sync_import_prices_for_hub
from app.services.catalog import catalog_sync_running, catalog_type_count, schedule_catalog_sync
from app.services.hub_groups import backfill_hub_market_groups_from_catalog
from app.services.market_groups import (
    full_group_sync_running,
    schedule_full_market_group_sync,
)
from app.sync.runner import schedule_structure_sync, structure_sync_running

router = APIRouter()


@router.get("/structure")
async def structure_sync_status() -> dict:
    return {"running": structure_sync_running()}


@router.post("/structure")
async def trigger_structure_sync() -> dict:
    """Pull WOMPSTAR market orders now (returns immediately; sync runs in background)."""
    return schedule_structure_sync()


@router.get("/import")
async def import_sync_status() -> dict:
    return {"running": import_sync_running()}


@router.get("/groups")
async def groups_sync_status() -> dict:
    return {"running": full_group_sync_running()}


@router.get("/catalog")
async def catalog_sync_status() -> dict:
    count = await catalog_type_count()
    return {
        "running": catalog_sync_running() or full_group_sync_running(),
        "type_count": count,
        "loaded": count > 0,
    }


@router.post("/catalog")
async def trigger_catalog_sync() -> dict:
    """Import all marketable types from EVE Ref archive (background, ~1–2 min)."""
    if catalog_sync_running():
        return {
            "status": "already_running",
            "message": "Catalog sync already in progress.",
        }
    schedule_catalog_sync()
    return {
        "status": "started",
        "message": "EVE Ref catalog import started (reference archive download).",
    }


@router.post("/groups")
async def trigger_groups_sync() -> dict:
    """Reload full market group tree from EVE Ref (background)."""
    if full_group_sync_running():
        return {
            "status": "already_running",
            "message": "Market group sync already in progress.",
        }
    schedule_full_market_group_sync()
    return {
        "status": "started",
        "message": "EVE Ref import started (groups + ~19k types, ~1–2 min).",
        "source": "everef",
    }


@router.post("/hub-groups")
async def trigger_hub_groups_sync(location_id: int | None = None) -> dict:
    """Backfill market_group_id on hub types from catalog (fixes empty orders-only tree)."""
    sid = int(location_id or settings.wompstar_structure_id or 0)
    if not sid:
        return {"status": "skipped", "reason": "MARKET_WOMPSTAR_STRUCTURE_ID unset"}
    from app.services.market_groups import sync_type_market_groups

    await sync_type_market_groups(location_id=sid)
    updated = await backfill_hub_market_groups_from_catalog(location_id=sid)
    return {"status": "ok", "location_id": sid, "types_updated": updated}


@router.get("/history")
async def history_sync_status() -> dict:
    return {"running": history_sync_running()}


@router.post("/history")
async def trigger_history_sync(location_id: int | None = None) -> dict:
    sid = int(location_id or settings.wompstar_structure_id or 0)
    if not sid:
        return {"status": "skipped", "reason": "MARKET_WOMPSTAR_STRUCTURE_ID unset"}
    if history_sync_running():
        return {"status": "already_running"}
    schedule_history_sync(location_id=sid)
    return {"status": "started", "location_id": sid}


@router.get("/contracts")
async def contracts_sync_status() -> dict:
    from app.services.contracts import issuer_corp_ids

    return {
        "running": contract_sync_running(),
        "issuer_corp_ids": issuer_corp_ids(),
    }


@router.post("/contracts")
async def trigger_contracts_sync() -> dict:
    from app.services.contracts import issuer_corp_ids

    if not issuer_corp_ids():
        return {
            "status": "skipped",
            "reason": "MARKET_WOMP_CONTRACT_ISSUER_CORP_ID(S) unset",
        }
    if contract_sync_running():
        return {"status": "already_running"}
    schedule_contract_sync()
    return {"status": "started", "issuer_corp_ids": issuer_corp_ids()}


@router.post("/import")
async def trigger_import_sync() -> dict:
    """Refresh Jita + Amarr best bid/ask for all types listed at WOMPSTAR."""
    sid = int(settings.wompstar_structure_id or 0)
    if not sid:
        return {"status": "skipped", "reason": "MARKET_WOMPSTAR_STRUCTURE_ID unset"}
    if import_sync_running():
        return {
            "status": "already_running",
            "message": "Import price sync already in progress.",
        }
    stats = await sync_import_prices_for_hub(location_id=sid)
    return {"status": "ok", **stats}
