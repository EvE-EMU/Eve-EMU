"""Coalition tools API — commerce, intelligence, operations, administration."""

from __future__ import annotations

import json
import logging
from decimal import Decimal

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import settings
from app.db.session import get_db
from app.models import (
    AppraisalReport,
    AuditProfile,
    AuthedStructure,
    BlueprintPublicContract,
    BuybackQuote,
    CorpMarketListing,
    CharacterCorpTitle,
    CharacterMarketOrder,
    FittingRecord,
    HrAccountFlag,
    HrBlacklistEntry,
    HrLeaveRequest,
    IndyHubJob,
    IndyBlueprint,
    IndyCopyRequest,
    IndyJobRecord,
    IndustryCalcJob,
    IndustrialBuildStructure,
    IndustrialProject,
    KillboardLeaderboard,
    MarketWatchItem,
    MaterialExchangeOrder,
    PniBill,
    PniStatement,
    RattingPayment,
    RattingTaxPeriod,
    SdeSystem,
    ServiceLink,
    SrpLoss,
    SsoUser,
)
from app.auth.deps import get_current_user
from app.schemas.storefront import StorefrontOrderCreate
from app.services.rbac import UserAuthContext
from app.services.storefront import (
    build_catalog,
    ensure_storefront_defaults,
    list_orders_for_buyer,
    notify_storefront_order,
    submit_storefront_order,
)

logger = logging.getLogger(__name__)
from app.schemas.tools import (
    AppraisalOut,
    AppraisalRequest,
    AuditProfileOut,
    AuthedStructureOut,
    BlueprintContractOut,
    BuybackLocationOut,
    BuybackRequest,
    CharacterMarketOrderOut,
    CorpMarketListingOut,
    CorpMarketOrderCreate,
    CorpMarketOrderOut,
    FittingCreateRequest,
    FittingOut,
    HrLeaveCreate,
    HrLeaveOut,
    IndustryCalcOut,
    IndustrialPlanRequest,
    IndustrialProjectCreate,
    IndyBlueprintOut,
    IndyCopyRequestOut,
    IndyHubJobOut,
    IndyJobRecordOut,
    JumpPlanRequest,
    JumpRangeDriveRequest,
    JumpRangeRequest,
    KillboardPilotOut,
    KillboardRowOut,
    RecentKillOut,
    MapActivityRequest,
    MarketWatchOut,
    MaterialExchangeOrderOut,
    PniStatementOut,
    RattingPeriodOut,
    RouteBookmarkCreate,
    RouteBookmarkOut,
    RoutePlanRequest,
    SdeSystemOut,
    SdeCompareIn,
    SdeCompareOut,
    SdeSkillCheckBatchIn,
    SdeTypeDetailOut,
    SdeTypeOut,
    ServiceLinkOut,
    SrpLossOut,
    ToolsHubOut,
)
from app.services.appraisal import new_share_token, run_appraisal, run_buyback, run_refine_compare
from app.services.buyback_locations import list_buyback_locations
from app.services.corp_market import submit_corp_market_order
from app.services.global_search import global_search
from app.services.market_browser import (
    fetch_market_history,
    fetch_market_orders,
    list_market_locations,
    warm_type_market_history,
)
from app.services.market_tracker import fetch_market_tracker
from app.services.industrial_planning import (
    calculate_build_plan,
    list_build_structures,
    list_projects,
    new_project_code,
)
from app.services.jump_drive import jump_range_systems, list_jump_ships, plan_jump_route
from app.services.janice import JANICE_MARKETS
from app.services.route_bookmarks import (
    create_route_bookmark,
    delete_route_bookmark,
    get_route_by_share_token,
    list_route_bookmarks,
)
from app.services.route_dock_locations import list_dock_locations
from app.services.route_planner import get_map_graph, get_map_status, jump_range, plan_route, search_systems, system_coords_map, system_display_map
from app.services.map_layout import get_map_atlas
from app.services.system_activity import get_system_activity, refresh_activity_snapshots
from app.services.sde_compare import compare_types, types_in_group
from app.services.sde_character_skills import get_character_skills_payload
from app.services.sde_skill_check import check_requirements, skill_check_types
from app.services.sde_type_detail import get_skill_requirements_for_type, get_type_detail
from app.services.sde_search import get_type, list_type_categories, search_types
from app.services.killboard_sync import (
    get_pilot_killboard_detail,
    get_recent_kills,
    killboard_is_stale,
    sync_killboard,
)
from app.services.zkill import fetch_alliance_stats, fetch_scope_stats

router = APIRouter(prefix="/tools", tags=["Tools"])


@router.get("/hub", response_model=ToolsHubOut)
async def tools_hub(db: AsyncSession = Depends(get_db)) -> ToolsHubOut:
    structures = (await db.scalars(select(AuthedStructure).order_by(AuthedStructure.structure_name))).all()
    categories = [
        {
            "slug": "commerce",
            "label": "Commerce",
            "tools": [
                {"slug": "buyback", "label": "Buyback", "public": True},
                {"slug": "appraisal", "label": "Appraisal", "public": True},
                {"slug": "market", "label": "Market Tracker"},
                {"slug": "market-browser", "label": "Market Browser", "public": True},
                {"slug": "corp-market", "label": "Corp Market"},
            ],
        },
        {
            "slug": "intelligence",
            "label": "Intelligence",
            "tools": [
                {"slug": "audit", "label": "Character Audit"},
                {"slug": "killboard", "label": "Killboard"},
                {"slug": "sde", "label": "SDE Browser", "public": True},
                {"slug": "map", "label": "Map & Routes", "public": True},
                {"slug": "routes", "label": "Route Bookmarks"},
            ],
        },
        {
            "slug": "operations",
            "label": "Industrial Planning",
            "tools": [
                {"slug": "ip-planner", "label": "Build Planner"},
                {"slug": "ip-blueprints", "label": "Blueprints & Contracts"},
                {"slug": "ip-projects", "label": "Project Costing"},
                {"slug": "ip-jobs", "label": "Industry Jobs"},
                {"slug": "ip-storefront", "label": "Storefront", "public": True},
                {"slug": "indy-copy", "label": "Copy Requests"},
            ],
        },
        {
            "slug": "administration",
            "label": "Administration",
            "tools": [
                {"slug": "services", "label": "Service Links"},
                {"slug": "ratting", "label": "Ratting Tax"},
                {"slug": "hr", "label": "HR Directorate"},
                {"slug": "pni", "label": "P&I Statements"},
                {"slug": "srp", "label": "SRP Program"},
            ],
        },
    ]
    return ToolsHubOut(
        categories=categories,
        authed_structures=[AuthedStructureOut.model_validate(s) for s in structures],
        markets=list(JANICE_MARKETS.keys()),
    )


# --- Commerce ---


@router.post("/commerce/appraisal", response_model=AppraisalOut)
async def create_appraisal(body: AppraisalRequest, db: AsyncSession = Depends(get_db)) -> AppraisalOut:
    result = await run_appraisal(
        text=body.text,
        sell_market=body.sell_market,
        buy_market=body.buy_market,
        session=db,
    )
    if result.get("error"):
        raise HTTPException(400, detail=result["error"])

    token = new_share_token()
    report = AppraisalReport(
        share_token=token,
        paste_text=body.text,
        sell_market=body.sell_market,
        buy_market=body.buy_market or body.sell_market,
        result_json=json.dumps(result),
    )
    db.add(report)
    await db.commit()
    await db.refresh(report)

    return AppraisalOut(
        id=report.id,
        share_token=token,
        share_url=f"{settings.public_base_url}/commerce?appraisal={token}",
        **result,
    )


@router.get("/commerce/appraisal/{share_token}", response_model=AppraisalOut)
async def get_appraisal(share_token: str, db: AsyncSession = Depends(get_db)) -> AppraisalOut:
    row = await db.scalar(select(AppraisalReport).where(AppraisalReport.share_token == share_token))
    if not row:
        raise HTTPException(404, detail="Appraisal not found")
    data = json.loads(row.result_json or "{}")
    return AppraisalOut(
        id=row.id,
        share_token=row.share_token,
        share_url=f"{settings.public_base_url}/commerce?appraisal={row.share_token}",
        **data,
    )


@router.post("/commerce/buyback", response_model=AppraisalOut)
async def create_buyback(body: BuybackRequest, db: AsyncSession = Depends(get_db)) -> AppraisalOut:
    token = new_share_token()
    result = await run_buyback(
        text=body.text,
        fee_pct=body.fee_pct,
        sell_market=body.sell_market,
        item_location=body.item_location,
        session=db,
        contract_code=token,
    )
    if result.get("error"):
        raise HTTPException(400, detail=result["error"])

    quote = BuybackQuote(
        share_token=token,
        paste_text=body.text,
        fee_pct=result.get("fee_pct", settings.default_buyback_fee_pct),
        sell_market=result.get("sell_market", body.sell_market),
        contract_value_isk=result.get("contract_value_isk", 0),
        result_json=json.dumps(result),
    )
    db.add(quote)
    await db.commit()
    await db.refresh(quote)

    return AppraisalOut(
        id=quote.id,
        share_token=token,
        share_url=f"{settings.public_base_url}/commerce?buyback={token}",
        **result,
    )


@router.get("/commerce/buyback/locations", response_model=list[BuybackLocationOut])
async def buyback_locations() -> list[BuybackLocationOut]:
    return [BuybackLocationOut(**loc) for loc in list_buyback_locations()]


@router.get("/commerce/buyback/{share_token}", response_model=AppraisalOut)
async def get_buyback(share_token: str, db: AsyncSession = Depends(get_db)) -> AppraisalOut:
    row = await db.scalar(select(BuybackQuote).where(BuybackQuote.share_token == share_token))
    if not row:
        raise HTTPException(404, detail="Buyback quote not found")
    data = json.loads(row.result_json or "{}")
    return AppraisalOut(
        id=row.id,
        share_token=row.share_token,
        share_url=f"{settings.public_base_url}/commerce?buyback={row.share_token}",
        **data,
    )


@router.post("/commerce/refine-compare", response_model=AppraisalOut)
async def refine_compare(body: AppraisalRequest, db: AsyncSession = Depends(get_db)) -> AppraisalOut:
    result = await run_refine_compare(
        text=body.text,
        market=body.sell_market,
        session=db,
    )
    if result.get("error"):
        raise HTTPException(400, detail=result["error"])
    return AppraisalOut(
        sell_market=result.get("sell_market", body.sell_market),
        buy_market=result.get("buy_market", body.sell_market),
        sell_market_label=result.get("sell_market_label", body.sell_market),
        buy_market_label=result.get("buy_market_label", body.sell_market),
        janice_configured=bool(result.get("janice_configured")),
        janice_code=result.get("janice_code"),
        janice_url=result.get("janice_url"),
        totals=result.get("totals") or {},
        unresolved=result.get("unresolved") or [],
        lines=result.get("lines") or [],
    )


@router.get("/commerce/market-watch", response_model=list[MarketWatchOut])
async def market_watch(
    hub: str = Query("jita"),
    system_id: int | None = Query(None),
    system_q: str = Query(""),
    item_q: str = Query(""),
    limit: int = Query(25, ge=1, le=50),
    db: AsyncSession = Depends(get_db),
) -> list[MarketWatchOut]:
    """Legacy seed table when Janice unavailable; otherwise live tracker rows."""
    if not system_q and not system_id and not item_q:
        rows = (await db.scalars(select(MarketWatchItem).order_by(MarketWatchItem.type_name))).all()
        if rows:
            return [MarketWatchOut.model_validate(r) for r in rows]

    tracker = await fetch_market_tracker(
        db,
        hub=hub,
        system_id=system_id,
        system_q=system_q,
        item_q=item_q,
        limit=limit,
    )
    out: list[MarketWatchOut] = []
    for row in tracker.get("rows") or []:
        out.append(
            MarketWatchOut(
                type_id=row["type_id"],
                type_name=row["type_name"],
                location_label=row.get("location_label") or tracker.get("system_label") or "",
                best_buy=row.get("local_buy"),
                best_sell=row.get("hub_sell"),
                spread_pct=row.get("spread_pct"),
            )
        )
    return out


@router.get("/commerce/market-tracker")
async def market_tracker(
    hub: str = Query("jita"),
    system_id: int | None = Query(None),
    system_q: str = Query(""),
    item_q: str = Query(""),
    limit: int = Query(25, ge=1, le=50),
    db: AsyncSession = Depends(get_db),
) -> dict:
    return await fetch_market_tracker(
        db,
        hub=hub,
        system_id=system_id,
        system_q=system_q,
        item_q=item_q,
        limit=limit,
    )


@router.post("/commerce/corp-market/orders", response_model=CorpMarketOrderOut)
async def create_corp_market_order(
    body: CorpMarketOrderCreate, db: AsyncSession = Depends(get_db)
) -> CorpMarketOrderOut:
    result = await submit_corp_market_order(
        db,
        buyer_character_name=body.buyer_character_name,
        buyer_character_id=body.buyer_character_id,
        type_id=body.type_id,
        type_name=body.type_name,
        quantity=body.quantity,
        unit_price_isk=body.unit_price_isk,
        delivery_location=body.delivery_location,
        notes=body.notes,
    )
    if result.get("error"):
        raise HTTPException(400, detail=result.get("message") or result["error"])
    await db.commit()
    return CorpMarketOrderOut(**result)


@router.get("/commerce/corp-market", response_model=list[CorpMarketListingOut])
async def corp_market(
    listing_type: str | None = None,
    db: AsyncSession = Depends(get_db),
) -> list[CorpMarketListingOut]:
    stmt = select(CorpMarketListing).where(CorpMarketListing.status == "open")
    if listing_type:
        stmt = stmt.where(CorpMarketListing.listing_type == listing_type)
    rows = (await db.scalars(stmt.order_by(CorpMarketListing.created_at.desc()))).all()
    return [CorpMarketListingOut.model_validate(r) for r in rows]


@router.get("/commerce/market-browser/locations")
async def market_browser_locations(db: AsyncSession = Depends(get_db)) -> dict:
    return await list_market_locations(db)


@router.get("/commerce/market-browser/orders")
async def market_browser_orders(
    kind: str = Query(..., description="region | station | structure | all_stations"),
    location_id: int = Query(..., ge=0),
    type_id: int = Query(..., ge=1),
    region_id: int | None = Query(None),
    order_type: str = Query("all"),
    db: AsyncSession = Depends(get_db),
) -> dict:
    return await fetch_market_orders(
        db,
        location_kind=kind,
        location_id=location_id,
        type_id=type_id,
        order_type=order_type,
        region_id=region_id,
    )


@router.get("/commerce/market-browser/history")
async def market_browser_history(
    region_id: int = Query(..., ge=1),
    type_id: int = Query(..., ge=1),
    max_days: int = Query(360, ge=7, le=365),
    db: AsyncSession = Depends(get_db),
) -> dict:
    result = await fetch_market_history(db, region_id=region_id, type_id=type_id, max_days=max_days)
    await db.commit()
    return result


@router.post("/commerce/market-browser/warm")
async def market_browser_warm(
    type_id: int = Query(..., ge=1),
    max_days: int = Query(360, ge=7, le=365),
    db: AsyncSession = Depends(get_db),
) -> dict:
    result = await warm_type_market_history(db, type_id=type_id, max_days=max_days)
    await db.commit()
    return result


# --- Intelligence ---


@router.get("/intelligence/sde/search", response_model=list[SdeTypeOut])
async def sde_search(
    q: str = Query("", min_length=0),
    limit: int = Query(50, ge=1, le=500),
    category: str = Query("", min_length=0),
    group: str = Query("", min_length=0),
    db: AsyncSession = Depends(get_db),
) -> list[SdeTypeOut]:
    rows = await search_types(db, q, limit=limit, category=category or None, group=group or None)
    return [SdeTypeOut(**r) for r in rows]


@router.get("/intelligence/sde/categories", response_model=list[str])
async def sde_categories(db: AsyncSession = Depends(get_db)) -> list[str]:
    return await list_type_categories(db)


@router.get("/intelligence/sde/types/{type_id}", response_model=SdeTypeOut)
async def sde_type(type_id: int, db: AsyncSession = Depends(get_db)) -> SdeTypeOut:
    row = await get_type(db, type_id)
    if not row:
        raise HTTPException(404, detail="Type not found")
    return SdeTypeOut(**row)


@router.get("/intelligence/sde/types/{type_id}/detail", response_model=SdeTypeDetailOut)
async def sde_type_detail(
    type_id: int,
    include_skill_check: bool = Query(True),
    db: AsyncSession = Depends(get_db),
) -> SdeTypeDetailOut:
    row = await get_type_detail(db, type_id)
    if not row:
        raise HTTPException(404, detail="Type not found")
    if include_skill_check:
        payload = await get_character_skills_payload(db)
        row["skill_check"] = check_requirements(
            row.get("requirements") or [], payload.get("best_skills") or {}
        )
    return SdeTypeDetailOut(**row)


@router.get("/intelligence/sde/character-skills")
async def sde_character_skills(db: AsyncSession = Depends(get_db)) -> dict:
    return await get_character_skills_payload(db)


@router.post("/intelligence/sde/skill-check")
async def sde_skill_check_batch(
    body: SdeSkillCheckBatchIn,
    db: AsyncSession = Depends(get_db),
) -> dict:
    payload = await get_character_skills_payload(db)
    best = payload.get("best_skills") or {}
    return await skill_check_types(db, body.type_ids, best)


@router.get("/intelligence/sde/group")
async def sde_group_types(
    group: str = Query(..., min_length=1),
    limit: int = Query(40, ge=1, le=100),
    db: AsyncSession = Depends(get_db),
) -> list[SdeTypeOut]:
    rows = await types_in_group(db, group, limit=limit)
    return [SdeTypeOut(**r) for r in rows]


@router.post("/intelligence/sde/compare", response_model=SdeCompareOut)
async def sde_compare(body: SdeCompareIn, db: AsyncSession = Depends(get_db)) -> SdeCompareOut:
    row = await compare_types(db, body.type_ids)
    if not row:
        raise HTTPException(400, detail="Need at least two valid type IDs to compare")
    return SdeCompareOut(**row)


@router.get("/intelligence/audit", response_model=list[AuditProfileOut])
async def audit_profiles(
    db: AsyncSession = Depends(get_db),
    auth: UserAuthContext = Depends(get_current_user),
) -> list[AuditProfileOut]:
    """Return audit profile for the logged-in pilot only (never demo coalition rows)."""
    row = await db.scalar(select(AuditProfile).where(AuditProfile.character_id == auth.character_id))
    if row:
        return [AuditProfileOut.model_validate(row)]
    user = await db.scalar(select(SsoUser).where(SsoUser.character_id == auth.character_id))
    if not user:
        return []
    return [
        AuditProfileOut(
            character_id=user.character_id,
            character_name=user.character_name,
            corporation_name=user.corporation_name or "",
            wallet_balance_isk=Decimal("0"),
            skill_points=0,
            assets_value_isk=Decimal("0"),
            snapshot_json="{}",
        )
    ]


@router.get("/intelligence/killboard", response_model=list[KillboardRowOut])
async def killboard(
    scope: str = "alliance",
    refresh: bool = Query(default=False),
    db: AsyncSession = Depends(get_db),
) -> list[KillboardRowOut]:
    scope_id = (
        settings.killboard_alliance_id if scope == "alliance" else settings.killboard_corporation_id
    )
    if refresh or await killboard_is_stale(db, scope, scope_id):
        try:
            await sync_killboard(db, scope=scope, scope_id=scope_id)
            await db.commit()
        except Exception:
            logger.exception("killboard auto-sync failed")
            await db.rollback()

    rows = (
        await db.scalars(
            select(KillboardLeaderboard)
            .where(KillboardLeaderboard.scope == scope, KillboardLeaderboard.scope_id == scope_id)
            .order_by(KillboardLeaderboard.isk_destroyed.desc())
        )
    ).all()
    return [KillboardRowOut.model_validate(r) for r in rows]


@router.post("/intelligence/killboard/sync")
async def killboard_sync(
    scope: str = "alliance",
    db: AsyncSession = Depends(get_db),
) -> dict:
    scope_id = (
        settings.killboard_alliance_id if scope == "alliance" else settings.killboard_corporation_id
    )
    result = await sync_killboard(db, scope=scope, scope_id=scope_id)
    await db.commit()
    rows = (
        await db.scalars(
            select(KillboardLeaderboard)
            .where(KillboardLeaderboard.scope == scope, KillboardLeaderboard.scope_id == scope_id)
            .order_by(KillboardLeaderboard.isk_destroyed.desc())
        )
    ).all()
    return {
        **result,
        "leaderboard": [KillboardRowOut.model_validate(r).model_dump() for r in rows],
    }


@router.get("/intelligence/killboard/stats")
async def killboard_stats(scope: str = "alliance") -> dict:
    scope_id = (
        settings.killboard_alliance_id if scope == "alliance" else settings.killboard_corporation_id
    )
    return await fetch_alliance_stats(scope_id) if scope == "alliance" else await fetch_scope_stats(scope, scope_id)


@router.get("/intelligence/killboard/recent", response_model=list[RecentKillOut])
async def killboard_recent(
    scope: str = "alliance",
    limit: int = Query(default=50, ge=1, le=100),
    db: AsyncSession = Depends(get_db),
) -> list[RecentKillOut]:
    rows = await get_recent_kills(db, scope=scope, limit=limit)
    return [RecentKillOut.model_validate(r) for r in rows]


@router.get("/intelligence/killboard/pilot/{character_id}", response_model=KillboardPilotOut)
async def killboard_pilot(
    character_id: int,
    scope: str = "alliance",
    db: AsyncSession = Depends(get_db),
) -> KillboardPilotOut:
    detail = await get_pilot_killboard_detail(db, character_id, scope=scope)
    return KillboardPilotOut.model_validate(detail)


@router.get("/intelligence/routes", response_model=list[RouteBookmarkOut])
async def routes(
    character_id: int | None = Query(None),
    db: AsyncSession = Depends(get_db),
) -> list[RouteBookmarkOut]:
    rows = await list_route_bookmarks(db, character_id=character_id)
    return [RouteBookmarkOut(**r) for r in rows]


@router.get("/intelligence/routes/share/{share_token}", response_model=RouteBookmarkOut)
async def route_by_share(share_token: str, db: AsyncSession = Depends(get_db)) -> RouteBookmarkOut:
    row = await get_route_by_share_token(db, share_token)
    if not row:
        raise HTTPException(status_code=404, detail="Route not found")
    return RouteBookmarkOut(**row)


@router.post("/intelligence/routes", response_model=RouteBookmarkOut)
async def create_route(body: RouteBookmarkCreate, db: AsyncSession = Depends(get_db)) -> RouteBookmarkOut:
    row = await create_route_bookmark(
        db,
        name=body.name,
        origin_system=body.origin_system,
        destination_system=body.destination_system,
        origin_system_id=body.origin_system_id,
        destination_system_id=body.destination_system_id,
        jumps=body.jumps,
        route_mode=body.route_mode,
        visibility=body.visibility,
        security_max=body.security_max,
        route_names=body.route_names,
        waypoint_system_ids=body.waypoint_system_ids,
        payload=body.payload,
        owner_character_id=body.owner_character_id,
        owner_character_name=body.owner_character_name,
        corporation_id=body.corporation_id,
        alliance_id=body.alliance_id,
    )
    await db.commit()
    return RouteBookmarkOut(**row)


@router.delete("/intelligence/routes/{bookmark_id}")
async def remove_route(
    bookmark_id: int,
    character_id: int | None = Query(None),
    db: AsyncSession = Depends(get_db),
) -> dict:
    ok = await delete_route_bookmark(db, bookmark_id, character_id=character_id)
    if not ok:
        raise HTTPException(status_code=404, detail="Route not found or not permitted")
    await db.commit()
    return {"deleted": True}


@router.get("/intelligence/map/dock-locations")
async def map_dock_locations(
    character_id: int | None = Query(None),
    db: AsyncSession = Depends(get_db),
) -> dict:
    return await list_dock_locations(db, character_id=character_id)


@router.get("/search")
async def search_all(
    q: str = Query("", min_length=0),
    limit: int = Query(20, ge=1, le=50),
    db: AsyncSession = Depends(get_db),
) -> dict:
    return await global_search(db, q, limit=limit)


@router.get("/intelligence/sde/systems", response_model=list[SdeSystemOut])
async def sde_systems(
    q: str = Query("", min_length=0),
    limit: int = Query(40, ge=1, le=200),
    db: AsyncSession = Depends(get_db),
) -> list[SdeSystemOut]:
    rows = await search_systems(db, q, limit=limit)
    return [SdeSystemOut(**r) for r in rows]


@router.post("/intelligence/map/route")
async def map_route(body: RoutePlanRequest, db: AsyncSession = Depends(get_db)) -> dict:
    return await plan_route(
        db,
        origin_system_id=body.origin_system_id,
        destination_system_id=body.destination_system_id,
        max_security=body.max_security,
        avoid_low_sec=body.avoid_low_sec,
        waypoint_system_ids=body.waypoint_system_ids,
    )


@router.post("/intelligence/map/jump-range")
async def map_jump_range(body: JumpRangeRequest, db: AsyncSession = Depends(get_db)) -> dict:
    return await jump_range(
        db,
        origin_system_id=body.origin_system_id,
        jump_range=body.jump_range,
        max_security=body.max_security,
    )


@router.get("/intelligence/map/graph")
async def map_graph(db: AsyncSession = Depends(get_db)) -> dict:
    return await get_map_graph(db)


@router.get("/intelligence/map/atlas")
async def map_atlas(db: AsyncSession = Depends(get_db)) -> dict:
    result = await get_map_atlas(db)
    await db.commit()
    return result


@router.get("/intelligence/map/status")
async def map_status(db: AsyncSession = Depends(get_db)) -> dict:
    return await get_map_status(db)


@router.post("/intelligence/map/activity")
async def map_activity(body: MapActivityRequest, db: AsyncSession = Depends(get_db)) -> dict:
    result = await get_system_activity(db, body.system_ids)
    await db.commit()
    return result


@router.get("/intelligence/map/jump-ships")
async def map_jump_ships() -> list[dict]:
    return list_jump_ships()


@router.post("/intelligence/map/jump-plan")
async def map_jump_plan(body: JumpPlanRequest, db: AsyncSession = Depends(get_db)) -> dict:
    systems = await _system_map_for_jump(db)
    coords = system_coords_map(systems)
    display = system_display_map(systems)
    names = {sid: s.name for sid, s in systems.items()}
    sec = {sid: s.security for sid, s in systems.items()}
    return plan_jump_route(
        ship_slug=body.ship_slug,
        origin_system_id=body.origin_system_id,
        destination_system_id=body.destination_system_id,
        jump_drive_calibration=body.jump_drive_calibration,
        jump_fuel_conservation=body.jump_fuel_conservation,
        jump_freighters=body.jump_freighters,
        coords=coords,
        system_names=names,
        system_security=sec,
        display_xy=display,
    )


@router.post("/intelligence/map/jump-drive-range")
async def map_jump_drive_range(body: JumpRangeDriveRequest, db: AsyncSession = Depends(get_db)) -> dict:
    systems = await _system_map_for_jump(db)
    coords = system_coords_map(systems)
    display = system_display_map(systems)
    names = {sid: s.name for sid, s in systems.items()}
    sec = {sid: s.security for sid, s in systems.items()}
    return jump_range_systems(
        ship_slug=body.ship_slug,
        origin_system_id=body.origin_system_id,
        jump_drive_calibration=body.jump_drive_calibration,
        coords=coords,
        system_names=names,
        system_security=sec,
        display_xy=display,
    )


async def _system_map_for_jump(db: AsyncSession) -> dict:
    rows = (await db.scalars(select(SdeSystem))).all()
    return {r.system_id: r for r in rows}


# --- Operations ---


@router.get("/operations/fittings", response_model=list[FittingOut])
async def fittings(
    db: AsyncSession = Depends(get_db),
    user: UserAuthContext = Depends(get_current_user),
) -> list[FittingOut]:
    from app.services.character_roster import roster_character_ids

    char_ids = await roster_character_ids(db, user.character_id)
    rows = (
        await db.scalars(
            select(FittingRecord)
            .where(FittingRecord.owner_character_id.in_(char_ids))
            .order_by(FittingRecord.owner_character_name, FittingRecord.name)
        )
    ).all()
    return [FittingOut.model_validate(r) for r in rows]


@router.get("/operations/blueprints", response_model=list[IndyBlueprintOut])
async def indy_blueprints(
    db: AsyncSession = Depends(get_db),
    user: UserAuthContext = Depends(get_current_user),
) -> list[IndyBlueprintOut]:
    from app.services.character_roster import roster_character_ids

    char_ids = await roster_character_ids(db, user.character_id)
    rows = (
        await db.scalars(
            select(IndyBlueprint)
            .where(IndyBlueprint.owner_character_id.in_(char_ids))
            .order_by(IndyBlueprint.owner_character_name, IndyBlueprint.type_name)
        )
    ).all()
    return [IndyBlueprintOut.model_validate(r) for r in rows]


@router.post("/operations/industry/sync")
async def industry_sync(
    db: AsyncSession = Depends(get_db),
    user: UserAuthContext = Depends(get_current_user),
) -> dict:
    from app.services.character_roster import roster_character_ids
    from app.services.industry_sync import sync_character_industry

    char_ids = sorted(await roster_character_ids(db, user.character_id))
    scope_errors: dict[str, str] = {}
    totals = {
        "fittings": 0,
        "blueprints": 0,
        "jobs": 0,
        "mining": 0,
        "characters": len(char_ids),
        "scope_errors": scope_errors,
    }
    for cid in char_ids:
        try:
            result = await sync_character_industry(db, cid, scope_errors=scope_errors)
            totals["fittings"] += int(result.get("fittings") or 0)
            totals["blueprints"] += int(result.get("blueprints") or 0)
            totals["jobs"] += int(result.get("jobs") or 0)
            totals["mining"] += int(result.get("mining") or 0)
            await db.commit()
        except Exception as exc:
            await db.rollback()
            logger.exception("industry sync failed for character %s", cid)
            scope_errors[str(cid)] = str(exc)[:200]
    return totals


@router.get("/operations/industry-calcs", response_model=list[IndustryCalcOut])
async def industry_calcs(db: AsyncSession = Depends(get_db)) -> list[IndustryCalcOut]:
    rows = (await db.scalars(select(IndustryCalcJob).order_by(IndustryCalcJob.id.desc()))).all()
    return [IndustryCalcOut.model_validate(r) for r in rows]


@router.get("/operations/indy-hub", response_model=list[IndyHubJobOut])
async def indy_hub_jobs(db: AsyncSession = Depends(get_db)) -> list[IndyHubJobOut]:
    rows = (await db.scalars(select(IndyHubJob).order_by(IndyHubJob.id.desc()))).all()
    return [IndyHubJobOut.model_validate(r) for r in rows]


@router.get("/operations/industry-jobs", response_model=list[IndyJobRecordOut])
async def indy_industry_jobs(
    db: AsyncSession = Depends(get_db),
    user: UserAuthContext = Depends(get_current_user),
) -> list[IndyJobRecordOut]:
    from app.services.character_roster import roster_character_ids

    char_ids = await roster_character_ids(db, user.character_id)
    rows = (
        await db.scalars(
            select(IndyJobRecord)
            .where(IndyJobRecord.owner_character_id.in_(char_ids))
            .order_by(IndyJobRecord.ends_at.desc(), IndyJobRecord.id.desc())
        )
    ).all()
    return [IndyJobRecordOut.model_validate(r) for r in rows]


@router.get("/operations/market-orders", response_model=list[CharacterMarketOrderOut])
async def character_market_orders(
    db: AsyncSession = Depends(get_db),
    user: UserAuthContext = Depends(get_current_user),
) -> list[CharacterMarketOrderOut]:
    from app.services.character_roster import roster_character_ids

    char_ids = await roster_character_ids(db, user.character_id)
    rows = (
        await db.scalars(
            select(CharacterMarketOrder)
            .where(CharacterMarketOrder.character_id.in_(char_ids))
            .order_by(CharacterMarketOrder.issued_at.desc(), CharacterMarketOrder.id.desc())
        )
    ).all()
    return [CharacterMarketOrderOut.model_validate(r) for r in rows]


@router.get("/operations/copy-requests", response_model=list[IndyCopyRequestOut])
async def indy_copy_requests(db: AsyncSession = Depends(get_db)) -> list[IndyCopyRequestOut]:
    rows = (await db.scalars(select(IndyCopyRequest).order_by(IndyCopyRequest.id.desc()))).all()
    return [IndyCopyRequestOut.model_validate(r) for r in rows]


@router.get("/operations/material-exchange", response_model=list[MaterialExchangeOrderOut])
async def material_exchange(db: AsyncSession = Depends(get_db)) -> list[MaterialExchangeOrderOut]:
    rows = (
        await db.scalars(select(MaterialExchangeOrder).order_by(MaterialExchangeOrder.id.desc()))
    ).all()
    return [MaterialExchangeOrderOut.model_validate(r) for r in rows]


@router.post("/operations/industrial-planning/calculate")
async def industrial_plan_calculate(
    body: IndustrialPlanRequest,
    db: AsyncSession = Depends(get_db),
    user: UserAuthContext = Depends(get_current_user),
) -> dict:
    return await calculate_build_plan(
        db,
        source_type=body.source_type,
        source_id=body.source_id,
        location_filter=body.location_filter,
        station_name=body.station_name,
        structure_id=body.structure_id,
        runs=body.runs,
        viewer_character_id=user.character_id,
        material_mode=body.material_mode,
        price_hub=body.price_hub,
        price_overrides=body.price_overrides or None,
        stock_assignments=body.stock_assignments or None,
        stock_location_ids=body.stock_location_ids or None,
        use_max_stock=body.use_max_stock,
        project_id=body.project_id,
        container_name=body.container_name,
    )


@router.post("/operations/fittings", response_model=FittingOut)
async def create_planner_fitting(
    body: FittingCreateRequest,
    db: AsyncSession = Depends(get_db),
    user: UserAuthContext = Depends(get_current_user),
) -> FittingRecord:
    from app.services.sde_search import get_type

    meta = await get_type(db, body.ship_type_id)
    ship_name = meta.get("name") if meta else f"Type {body.ship_type_id}"
    row = FittingRecord(
        name=body.name.strip(),
        ship_type_id=body.ship_type_id,
        ship_type_name=str(ship_name)[:128],
        doctrine_slug="",
        eft_text=body.eft_text or "",
        tags_json="{}",
        public=False,
        owner_character_id=user.character_id,
        owner_character_name=user.character_name[:128],
        esi_fitting_id=None,
    )
    db.add(row)
    await db.commit()
    await db.refresh(row)
    return row


@router.get("/operations/industrial-planning/structures")
async def industrial_plan_structures(
    location_filter: str = Query("all"),
    station_name: str | None = Query(None),
    db: AsyncSession = Depends(get_db),
) -> list[dict]:
    rows = await list_build_structures(db, location_filter=location_filter, station_name=station_name)
    return [
        {
            "structure_id": r.structure_id,
            "structure_name": r.structure_name,
            "system_name": r.system_name,
            "location_label": r.location_label,
            "material_bonus_pct": r.material_bonus_pct,
            "time_bonus_pct": r.time_bonus_pct,
            "tax_pct": r.tax_pct,
        }
        for r in rows
    ]


@router.get("/operations/industrial-planning/projects")
async def industrial_projects(db: AsyncSession = Depends(get_db)) -> list[dict]:
    return await list_projects(db)


@router.post("/operations/industrial-planning/projects")
async def create_industrial_project(
    body: IndustrialProjectCreate, db: AsyncSession = Depends(get_db)
) -> dict:
    row = IndustrialProject(
        project_code=new_project_code(),
        name=body.name,
        container_name=body.container_name,
        owner_character_name=body.owner_character_name,
        notes=body.notes,
    )
    db.add(row)
    await db.commit()
    await db.refresh(row)
    mfg_bridge: dict = {"skipped": True, "reason": "no_session_in_body"}
    try:
        from app.services.mfg_bridge import create_mfg_project_from_emums

        # Soft bridge — only when client forwards an mfg session (optional field).
        session = getattr(body, "mfg_session", None) or None
        mfg_bridge = await create_mfg_project_from_emums(
            hull_name=body.name or row.project_code,
            material_cost=0,
            customer_character_name=body.owner_character_name or "",
            source="emums_industrial_project",
            session_token=session,
        )
    except Exception:
        mfg_bridge = {"ok": False, "error": "bridge_failed"}
    return {
        "id": row.id,
        "project_code": row.project_code,
        "name": row.name,
        "container_name": row.container_name,
        "mfg_bridge": mfg_bridge,
        "industrial_url": "https://eve-emu.com/industrial?tab=projects",
    }


@router.get("/operations/blueprint-contracts", response_model=list[BlueprintContractOut])
async def blueprint_contracts(db: AsyncSession = Depends(get_db)) -> list[BlueprintContractOut]:
    rows = (
        await db.scalars(select(BlueprintPublicContract).order_by(BlueprintPublicContract.blueprint_name))
    ).all()
    return [BlueprintContractOut.model_validate(r) for r in rows]


@router.get("/operations/storefront")
async def storefront_catalog(db: AsyncSession = Depends(get_db)) -> dict:
    await ensure_storefront_defaults(db)
    return await build_catalog(db, public=True)


@router.post("/commerce/storefront/orders")
async def create_storefront_order(
    body: StorefrontOrderCreate,
    db: AsyncSession = Depends(get_db),
    auth: UserAuthContext = Depends(get_current_user),
) -> dict:
    if not auth.has_permission("industrial.storefront"):
        raise HTTPException(
            status_code=403,
            detail="Storefront checkout requires coalition blue or member access.",
        )
    user = await db.scalar(select(SsoUser).where(SsoUser.character_id == auth.character_id))
    buyer_name = (user.character_name if user and user.character_name else "") or auth.character_name
    result = await submit_storefront_order(
        db,
        buyer_character_id=int(auth.character_id),
        buyer_character_name=buyer_name,
        pickup_location_id=body.pickup_location_id,
        cart_lines=[line.model_dump() for line in body.lines],
        notes=body.notes,
        notify=False,
    )
    if result.get("error"):
        raise HTTPException(400, detail=result.get("message") or result["error"])
    await db.commit()
    order_id = int(result["id"])
    result = await notify_storefront_order(db, order_id)
    await db.commit()
    # Best-effort ManufacturingProject / ProjectQuote on core industrial suite
    try:
        from app.services.mfg_bridge import create_mfg_project_from_emums

        lines = result.get("lines") or []
        materials = [
            {
                "type_id": ln.get("type_id"),
                "type_name": ln.get("name"),
                "quantity": ln.get("quantity"),
                "unit_cost": ln.get("unit_price_isk"),
            }
            for ln in lines
            if isinstance(ln, dict)
        ]
        hull = (
            (materials[0].get("type_name") if materials else None)
            or f"Storefront order #{order_id}"
        )
        bridge = await create_mfg_project_from_emums(
            hull_name=str(hull),
            sale_price=float(result.get("total_isk") or 0),
            material_cost=float(result.get("total_isk") or 0),
            customer_character_name=buyer_name,
            source="emums_storefront",
            materials=materials,
            create_quote=True,
            session_token=None,  # no director session on buyer checkout
        )
        result["mfg_bridge"] = bridge
        result["industrial_url"] = "https://eve-emu.com/industrial?tab=projects"
    except Exception as exc:
        result["mfg_bridge"] = {"ok": False, "error": str(exc)}
    return result


@router.get("/commerce/storefront/my-orders")
async def storefront_my_orders(
    db: AsyncSession = Depends(get_db),
    auth: UserAuthContext = Depends(get_current_user),
) -> dict:
    orders = await list_orders_for_buyer(db, buyer_character_id=int(auth.character_id))
    return {"orders": orders}


@router.get("/operations/structure-fuel")
async def structure_fuel_board_api(
    refresh: bool = False,
    db: AsyncSession = Depends(get_db),
    auth: UserAuthContext = Depends(get_current_user),
) -> dict:
    from app.services.structure_fuel import structure_fuel_board

    return await structure_fuel_board(db, refresh=refresh)


@router.post("/operations/structure-fuel/sync")
async def structure_fuel_sync_api(
    db: AsyncSession = Depends(get_db),
    auth: UserAuthContext = Depends(get_current_user),
) -> dict:
    from app.services.structure_fuel import sync_corp_structure_fuel

    _ = auth  # requires SSO session; ESI uses corp tokens with structures scope
    result = await sync_corp_structure_fuel(db)
    await db.commit()
    return result


@router.get("/operations/moon-timing")
async def moon_timing_api(
    days: int = 45,
    idle_days: int = 7,
    db: AsyncSession = Depends(get_db),
) -> dict:
    from app.services.moon_timing import moon_mining_timing

    return await moon_mining_timing(db, days=days, idle_days=idle_days)


# --- Administration ---


@router.get("/administration/services", response_model=list[ServiceLinkOut])
async def service_links(db: AsyncSession = Depends(get_db)) -> list[ServiceLinkOut]:
    rows = (
        await db.scalars(select(ServiceLink).where(ServiceLink.active).order_by(ServiceLink.service))
    ).all()
    return [ServiceLinkOut.model_validate(r) for r in rows]


@router.get("/administration/ratting", response_model=list[RattingPeriodOut])
async def ratting_periods(db: AsyncSession = Depends(get_db)) -> list[RattingPeriodOut]:
    rows = (await db.scalars(select(RattingTaxPeriod).order_by(RattingTaxPeriod.id.desc()))).all()
    return [RattingPeriodOut.model_validate(r) for r in rows]


@router.get("/administration/ratting/{period_id}/payments")
async def ratting_payments(period_id: int, db: AsyncSession = Depends(get_db)) -> list[dict]:
    rows = (
        await db.scalars(select(RattingPayment).where(RattingPayment.period_id == period_id))
    ).all()
    return [
        {
            "character_name": r.character_name,
            "bounty_isk": str(r.bounty_isk),
            "tax_due_isk": str(r.tax_due_isk),
            "paid_isk": str(r.paid_isk),
            "status": r.status,
        }
        for r in rows
    ]


@router.get("/administration/hr/leaves", response_model=list[HrLeaveOut])
async def hr_leaves(db: AsyncSession = Depends(get_db)) -> list[HrLeaveOut]:
    rows = (await db.scalars(select(HrLeaveRequest).order_by(HrLeaveRequest.start_date.desc()))).all()
    return [HrLeaveOut.model_validate(r) for r in rows]


@router.post("/administration/hr/leaves", response_model=HrLeaveOut)
async def create_hr_leave(body: HrLeaveCreate, db: AsyncSession = Depends(get_db)) -> HrLeaveOut:
    row = HrLeaveRequest(
        character_name=body.character_name,
        character_id=body.character_id,
        start_date=body.start_date,
        end_date=body.end_date,
        reason=body.reason,
    )
    db.add(row)
    await db.commit()
    await db.refresh(row)
    return HrLeaveOut.model_validate(row)


@router.get("/administration/hr/blacklist")
async def hr_blacklist(db: AsyncSession = Depends(get_db)) -> list[dict]:
    rows = (
        await db.scalars(select(HrBlacklistEntry).where(HrBlacklistEntry.active))
    ).all()
    return [{"character_name": r.character_name, "reason": r.reason, "added_by": r.added_by} for r in rows]


@router.get("/administration/hr/flags")
async def hr_flags(db: AsyncSession = Depends(get_db)) -> list[dict]:
    rows = (await db.scalars(select(HrAccountFlag).where(HrAccountFlag.active))).all()
    return [
        {
            "character_name": r.target_character_name,
            "flag_key": r.flag_key,
            "flag_label": r.flag_label,
            "color": r.color,
            "notes": r.notes,
        }
        for r in rows
    ]


@router.get("/administration/pni", response_model=list[PniStatementOut])
async def pni_statements(db: AsyncSession = Depends(get_db)) -> list[PniStatementOut]:
    rows = (await db.scalars(select(PniStatement).order_by(PniStatement.id.desc()))).all()
    return [PniStatementOut.model_validate(r) for r in rows]


@router.get("/administration/pni/{statement_id}/bills")
async def pni_bills(statement_id: int, db: AsyncSession = Depends(get_db)) -> list[dict]:
    rows = (await db.scalars(select(PniBill).where(PniBill.statement_id == statement_id))).all()
    return [
        {
            "bill_type": r.bill_type,
            "description": r.description,
            "amount_isk": str(r.amount_isk),
            "status": r.status,
            "due_at": r.due_at.isoformat() if r.due_at else None,
        }
        for r in rows
    ]


@router.get("/administration/srp", response_model=list[SrpLossOut])
async def srp_losses(db: AsyncSession = Depends(get_db)) -> list[SrpLossOut]:
    rows = (await db.scalars(select(SrpLoss).order_by(SrpLoss.id.desc()))).all()
    return [SrpLossOut.model_validate(r) for r in rows]


@router.get("/structures", response_model=list[AuthedStructureOut])
async def authed_structures(db: AsyncSession = Depends(get_db)) -> list[AuthedStructureOut]:
    rows = (await db.scalars(select(AuthedStructure).order_by(AuthedStructure.structure_name))).all()
    return [AuthedStructureOut.model_validate(r) for r in rows]


# --- Awesome-eve combined suite (live ESI / zKill / market / audit DB) ---


@router.get("/suite/catalog")
async def suite_catalog() -> dict:
    from app.services.awesome_suite import catalog

    return catalog()


@router.post("/suite/intel")
async def suite_intel(body: dict) -> dict:
    from app.services.awesome_suite import intel_paste

    text = str(body.get("text") or "")
    with_zkill = body.get("with_zkill", True)
    return await intel_paste(text, with_zkill=bool(with_zkill))


@router.post("/suite/trade-margins")
async def suite_trade_margins(
    body: dict,
    db: AsyncSession = Depends(get_db),
) -> dict:
    from app.services.awesome_suite import trade_margins

    type_ids = body.get("type_ids") or []
    if not isinstance(type_ids, list):
        type_ids = []
    return await trade_margins(
        db,
        text=str(body.get("text") or ""),
        type_ids=[int(x) for x in type_ids if str(x).isdigit() or isinstance(x, int)],
        hub=str(body.get("hub") or "jita"),
        limit=int(body.get("limit") or 40),
    )


@router.get("/suite/corp-who")
async def suite_corp_who(
    corporation_id: int | None = None,
    corporation_name: str = "",
) -> dict:
    from app.services.awesome_suite import corp_who

    return await corp_who(corporation_id=corporation_id, corporation_name=corporation_name)


@router.get("/suite/battle-report")
async def suite_battle_report(system_id: int, limit: int = 50) -> dict:
    from app.services.awesome_suite import battle_report

    return await battle_report(system_id, limit=min(max(limit, 1), 100))


@router.get("/suite/skill-queues")
async def suite_skill_queues(
    db: AsyncSession = Depends(get_db),
    user: UserAuthContext = Depends(get_current_user),
) -> dict:
    from app.services.awesome_suite import roster_skill_snapshot
    from app.services.character_roster import roster_character_ids

    ids = await roster_character_ids(db, user.character_id)
    return await roster_skill_snapshot(db, list(ids))


@router.post("/suite/gate-camp-route")
async def suite_gate_camp_route(body: dict, db: AsyncSession = Depends(get_db)) -> dict:
    from app.services.awesome_suite import gate_camp_route

    return await gate_camp_route(
        db,
        origin_system_id=int(body.get("origin_system_id") or 0),
        destination_system_id=int(body.get("destination_system_id") or 0),
        avoid_low_sec=bool(body.get("avoid_low_sec")),
    )


@router.post("/suite/haul-finder")
async def suite_haul_finder(body: dict, db: AsyncSession = Depends(get_db)) -> dict:
    from app.services.awesome_suite import haul_finder

    return await haul_finder(
        db,
        text=str(body.get("text") or ""),
        buy_hub=str(body.get("buy_hub") or "jita"),
        sell_hub=str(body.get("sell_hub") or "amarr"),
        limit=int(body.get("limit") or 30),
        min_margin_pct=float(body.get("min_margin_pct") or 5.0),
    )


@router.get("/suite/structure-board")
async def suite_structure_board(db: AsyncSession = Depends(get_db)) -> dict:
    from app.services.awesome_suite import structure_board

    return await structure_board(db)


@router.get("/suite/ship-compare")
async def suite_ship_compare(
    type_a: int,
    type_b: int,
    db: AsyncSession = Depends(get_db),
) -> dict:
    from app.services.awesome_suite import ship_compare

    return await ship_compare(db, type_a, type_b)


@router.post("/suite/insurance-check")
async def suite_insurance_check(body: dict, db: AsyncSession = Depends(get_db)) -> dict:
    from app.services.awesome_suite import insurance_check

    type_ids = body.get("type_ids") or []
    if not isinstance(type_ids, list):
        type_ids = []
    return await insurance_check(
        db,
        text=str(body.get("text") or ""),
        type_ids=[int(x) for x in type_ids if str(x).isdigit() or isinstance(x, int)],
        hub=str(body.get("hub") or "jita"),
    )
