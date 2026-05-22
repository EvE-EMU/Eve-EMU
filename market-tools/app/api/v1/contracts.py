from fastapi import APIRouter, HTTPException, Query

from app.config import settings
from app.services.contracts import (
    contract_margin_rows,
    contract_sync_running,
    issuer_corp_ids,
    schedule_contract_sync,
    sync_all_contracts,
)

router = APIRouter()


@router.get("/margins")
async def contract_margins(
    location_id: int | None = None,
    limit: int = Query(500, ge=1, le=2000),
) -> dict:
    loc = location_id or settings.wompstar_structure_id
    if not loc:
        raise HTTPException(503, "WOMPSTAR structure not configured")
    rows = await contract_margin_rows(location_id=int(loc), limit=limit)
    return {
        "location_id": loc,
        "issuer_corp_ids": issuer_corp_ids(),
        "rows": rows,
    }


@router.get("/status")
async def contracts_status() -> dict:
    return {
        "running": contract_sync_running(),
        "issuer_corp_ids": issuer_corp_ids(),
        "configured": bool(issuer_corp_ids()),
    }


@router.post("/sync")
async def trigger_contract_sync() -> dict:
    if not issuer_corp_ids():
        return {
            "status": "skipped",
            "reason": "Set MARKET_WOMP_CONTRACT_ISSUER_CORP_ID or MARKET_WOMP_CONTRACT_ISSUER_CORP_IDS",
        }
    if not settings.esi_configured():
        return {"status": "skipped", "reason": "esi_not_configured"}
    if contract_sync_running():
        return {"status": "already_running"}
    schedule_contract_sync()
    return {"status": "started", "issuer_corp_ids": issuer_corp_ids()}


@router.post("/sync/now")
async def contract_sync_now() -> dict:
    """Synchronous contract pull (may take a minute)."""
    if not issuer_corp_ids():
        return {
            "status": "skipped",
            "reason": "Set MARKET_WOMP_CONTRACT_ISSUER_CORP_ID or MARKET_WOMP_CONTRACT_ISSUER_CORP_IDS",
        }
    if not settings.esi_configured():
        return {"status": "skipped", "reason": "esi_not_configured"}
    stats = await sync_all_contracts()
    return {"status": "ok", **stats}
