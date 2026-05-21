from fastapi import APIRouter
from sqlalchemy import func, select

from app.config import settings
from app.services.market_history import resolve_hub_region_id
from app.db.models import MarketOrder, SyncRun
from app.db.session import session_scope

router = APIRouter()


@router.get("/meta")
async def meta() -> dict:
    esi_ok = settings.esi_configured()
    order_count = 0
    last_sync = None
    async with session_scope() as session:
        if settings.wompstar_structure_id:
            order_count = await session.scalar(
                select(func.count())
                .select_from(MarketOrder)
                .where(MarketOrder.location_id == settings.wompstar_structure_id)
            ) or 0
        run = await session.scalar(
            select(SyncRun)
            .where(SyncRun.job == "structure_orders")
            .order_by(SyncRun.id.desc())
            .limit(1)
        )
        if run:
            last_sync = {
                "finished_at": run.finished_at.isoformat() if run.finished_at else None,
                "ok": run.ok,
                "detail": run.detail,
            }
    return {
        "public_base_url": settings.public_base_url,
        "sync": {
            "esi_configured": esi_ok,
            "esi_source": "aa_token_bridge" if settings.use_aa_token else "refresh_token",
            "esi_character": settings.esi_character_name,
            "esi_token_id": settings.esi_token_id or None,
            "structure_configured": bool(settings.wompstar_structure_id),
            "cached_orders": int(order_count),
            "last_structure_sync": last_sync,
        },
        "wompstar": {
            "structure_id": settings.wompstar_structure_id,
            "name": settings.wompstar_structure_name,
            "system_id": settings.wompstar_system_id,
            "region_id": await resolve_hub_region_id(),
        },
        "import": {
            "region_id": settings.default_import_region_id,
            "station_id": settings.default_import_station_id,
        },
        "buyback_url": settings.buyback_public_url,
        "tools": [
            {"path": "/margin_finder", "label": "Margin finder"},
            {"path": "/market_trends", "label": "Market trends"},
            {"path": "/contract_price", "label": "Contract prices"},
            {"path": "/tradeVol_type", "label": "Trade volume"},
            {"path": "/price_compare", "label": "Price compare"},
            {"path": "/pi_rank", "label": "PI rank"},
            {"path": "/market-browser", "label": "Market browser"},
            {"path": "/appraisal", "label": "Appraisal"},
        ],
    }
