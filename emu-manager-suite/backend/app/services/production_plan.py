"""Ravworks-style production plan — materials, stock, Jita prices, jobs, profit."""

from __future__ import annotations

import math
import secrets
from decimal import Decimal
from typing import Any

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.member_audit import CharacterAsset
from app.models.tools import (
    FittingRecord,
    IndustrialBuildStructure,
    IndyBlueprint,
    SdeTypeIndex,
)
from app.services.character_roster import roster_character_ids
from app.services.industrial_planning import list_build_structures
from app.services.janice import (
    JANICE_MARKETS,
    janice_base_job_costs,
    janice_configured,
    janice_create_appraisal,
)
from app.services.market_prices import hub_prices_for_types
from app.services.sde_industry import (
    IndustryRecipe,
    RecipeMaterial,
    apply_me,
    blueprint_for_product,
    recipe_for_blueprint,
    type_name,
)

SALES_TAX_RATE = Decimal("0.075")
DEFAULT_JOB_COST_RATE = Decimal("0.048")


async def _resolve_recipe(
    session: AsyncSession,
    *,
    source_type: str,
    source_id: int,
) -> tuple[IndustryRecipe | None, str, int, int, int]:
    """Return recipe, display name, product_type_id, me, te."""
    me, te = 0, 0
    if source_type == "fitting":
        row = await session.get(FittingRecord, source_id)
        if not row:
            return None, "", 0, 0, 0
        product_type_id = int(row.ship_type_id)
        recipe = blueprint_for_product(product_type_id)
        label = f"{row.ship_type_name} ({row.name})"
        return recipe, label, product_type_id, me, te

    if source_type == "blueprint":
        row = await session.get(IndyBlueprint, source_id)
        if not row:
            return None, "", 0, 0, 0
        me, te = int(row.material_efficiency or 0), int(row.time_efficiency or 0)
        recipe = recipe_for_blueprint(int(row.type_id))
        return recipe, row.type_name, int(row.type_id), me, te

    if source_type == "product":
        product_type_id = source_id
        recipe = blueprint_for_product(product_type_id)
        return recipe, type_name(product_type_id), product_type_id, me, te

    return None, "", 0, 0, 0


async def _stock_by_type(
    session: AsyncSession,
    character_ids: set[int],
    *,
    location_ids: set[int] | None = None,
) -> dict[int, int]:
    q = select(CharacterAsset.type_id, func.sum(CharacterAsset.quantity)).where(
        CharacterAsset.character_id.in_(character_ids)
    )
    if location_ids:
        q = q.where(CharacterAsset.location_id.in_(location_ids))
    q = q.group_by(CharacterAsset.type_id)
    rows = (await session.execute(q)).all()
    return {int(tid): int(qty or 0) for tid, qty in rows if int(tid or 0) > 0}


async def resolve_project_warehouse_location_ids(
    session: AsyncSession,
    character_ids: set[int],
    *,
    project_id: int | None = None,
    container_name: str | None = None,
) -> tuple[set[int] | None, str]:
    """Resolve station-warehouse / project container item_ids for stock pull.

    Items stored *inside* a named container have ``location_id == container.item_id``.
    Returns (location_ids or None for all stock, resolved_container_label).
    """
    from sqlalchemy import or_

    from app.models.tools import IndustrialProject

    name = (container_name or "").strip()
    if project_id and not name:
        project = await session.get(IndustrialProject, int(project_id))
        if project:
            name = (project.container_name or "").strip()

    if not name or not character_ids:
        return None, ""

    containers = (
        await session.scalars(
            select(CharacterAsset).where(
                CharacterAsset.character_id.in_(character_ids),
                or_(
                    CharacterAsset.custom_name == name,
                    CharacterAsset.type_name == name,
                    CharacterAsset.custom_name.ilike(f"%{name}%"),
                    CharacterAsset.type_name.ilike(f"%{name}%"),
                ),
            )
        )
    ).all()
    if not containers:
        return set(), name

    # Stock lives inside the container (location_id = container item_id).
    return {int(c.item_id) for c in containers if int(c.item_id or 0) > 0}, name


async def _volumes(session: AsyncSession, type_ids: set[int]) -> dict[int, float]:
    if not type_ids:
        return {}
    rows = (await session.scalars(select(SdeTypeIndex).where(SdeTypeIndex.type_id.in_(type_ids)))).all()
    return {int(r.type_id): float(r.volume_m3 or 0) for r in rows}


def _expand_materials_base(
    recipe: IndustryRecipe,
    *,
    runs: int,
    me: int,
    structure_bonus_pct: float,
    depth: int = 0,
) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    """Flatten to base materials; return (material lines, job lines)."""
    if depth > 12:
        return [], []
    scaled = [
        RecipeMaterial(m.type_id, m.name, m.quantity * runs)
        for m in apply_me(recipe.materials, me, structure_bonus_pct=structure_bonus_pct)
    ]
    jobs: list[dict[str, Any]] = [
        {
            "name": recipe.blueprint_name,
            "blueprint_type_id": recipe.blueprint_type_id,
            "product_type_id": recipe.product_type_id,
            "product_name": recipe.product_name,
            "runs": runs,
            "me": me,
            "activity": recipe.activity_name,
            "time_seconds": recipe.time_seconds * runs,
        }
    ]
    merged: dict[int, dict[str, Any]] = {}

    def _add(tid: int, name: str, qty: int, *, is_component: bool) -> None:
        row = merged.get(tid)
        if not row:
            merged[tid] = {
                "type_id": tid,
                "name": name,
                "required_qty": 0,
                "is_component": is_component,
            }
        merged[tid]["required_qty"] += qty
        if is_component:
            merged[tid]["is_component"] = True

    for mat in scaled:
        sub = blueprint_for_product(mat.type_id)
        if sub and mat.type_id != recipe.product_type_id:
            sub_mats, sub_jobs = _expand_materials_base(
                sub, runs=mat.quantity, me=0, structure_bonus_pct=structure_bonus_pct, depth=depth + 1
            )
            jobs.extend(sub_jobs)
            for sm in sub_mats:
                _add(sm["type_id"], sm["name"], sm["required_qty"], is_component=sm.get("is_component", False))
        else:
            _add(mat.type_id, mat.name, mat.quantity, is_component=False)

    return list(merged.values()), jobs


def _expand_materials_components(
    recipe: IndustryRecipe,
    *,
    runs: int,
    me: int,
    structure_bonus_pct: float,
) -> tuple[list[dict[str, Any]], list[dict[str, Any]], list[dict[str, Any]]]:
    """Keep build components as separate lines; return materials, jobs, produced_parts."""
    scaled = apply_me(recipe.materials, me, structure_bonus_pct=structure_bonus_pct)
    materials: list[dict[str, Any]] = []
    produced: list[dict[str, Any]] = []
    jobs: list[dict[str, Any]] = [
        {
            "name": recipe.blueprint_name,
            "blueprint_type_id": recipe.blueprint_type_id,
            "product_type_id": recipe.product_type_id,
            "product_name": recipe.product_name,
            "runs": runs,
            "me": me,
            "activity": recipe.activity_name,
            "time_seconds": recipe.time_seconds * runs,
            "is_end_product": True,
        }
    ]
    for mat in scaled:
        qty = mat.quantity * runs
        sub = blueprint_for_product(mat.type_id)
        is_comp = sub is not None and mat.type_id != recipe.product_type_id
        materials.append(
            {
                "type_id": mat.type_id,
                "name": mat.name,
                "required_qty": qty,
                "is_component": is_comp,
            }
        )
        if is_comp and sub:
            produced.append(
                {
                    "type_id": mat.type_id,
                    "name": mat.name,
                    "group": type_name(mat.type_id),
                    "runs": qty,
                    "amount": qty,
                    "time_seconds": sub.time_seconds * qty,
                    "blueprint_type_id": sub.blueprint_type_id,
                }
            )
            jobs.append(
                {
                    "name": sub.blueprint_name,
                    "blueprint_type_id": sub.blueprint_type_id,
                    "product_type_id": sub.product_type_id,
                    "product_name": sub.product_name,
                    "runs": qty,
                    "me": 0,
                    "activity": sub.activity_name,
                    "time_seconds": sub.time_seconds * qty,
                    "is_end_product": False,
                }
            )
    return materials, jobs, produced


def _job_cost(material_buy_total: float, structure: IndustrialBuildStructure) -> float:
    tax = Decimal(str(structure.tax_pct or 0)) / Decimal("100")
    return float(Decimal(str(material_buy_total)) * DEFAULT_JOB_COST_RATE * (Decimal("1") + tax))


def _apply_time_bonus(seconds: int, te: int, structure: IndustrialBuildStructure) -> int:
    te_factor = max(0.2, 1.0 - min(te, 20) * 0.02)
    struct_factor = max(0.2, 1.0 - float(structure.time_bonus_pct or 0) / 100.0)
    return max(60, int(seconds * te_factor * struct_factor))


async def calculate_production_plan(
    session: AsyncSession,
    *,
    viewer_character_id: int,
    source_type: str,
    source_id: int,
    runs: int = 1,
    material_mode: str = "base",
    location_filter: str = "all",
    station_name: str | None = None,
    structure_id: int | None = None,
    price_hub: str = "jita",
    price_overrides: dict[int, Decimal] | None = None,
    stock_assignments: dict[int, int] | None = None,
    stock_location_ids: list[int] | None = None,
    use_max_stock: bool = True,
    project_id: int | None = None,
    container_name: str | None = None,
    sales_tax_rate: Decimal | None = None,
) -> dict[str, Any]:
    runs = max(1, int(runs))
    recipe, source_name, _product_tid, me, te = await _resolve_recipe(
        session, source_type=source_type, source_id=source_id
    )
    if not recipe:
        return {"error": "no_recipe", "message": "No SDE manufacturing recipe found for this item."}

    structures = await list_build_structures(
        session, location_filter=location_filter, station_name=station_name
    )
    if not structures:
        return {"error": "no_structures", "source_name": source_name}

    structure = structures[0]
    if structure_id:
        match = next((s for s in structures if s.structure_id == structure_id), None)
        if match:
            structure = match

    bonus = float(structure.material_bonus_pct or 0)
    if material_mode == "components":
        raw_materials, jobs, produced_parts = _expand_materials_components(
            recipe, runs=runs, me=me, structure_bonus_pct=bonus
        )
    else:
        raw_materials, jobs = _expand_materials_base(
            recipe, runs=runs, me=me, structure_bonus_pct=bonus
        )
        produced_parts = []

    char_ids = set(await roster_character_ids(session, viewer_character_id))
    warehouse_locs, warehouse_label = await resolve_project_warehouse_location_ids(
        session,
        char_ids,
        project_id=project_id,
        container_name=container_name,
    )
    if stock_location_ids:
        loc_filter: set[int] | None = set(stock_location_ids)
    elif warehouse_locs is not None:
        loc_filter = warehouse_locs
    else:
        loc_filter = None
    stock_map = await _stock_by_type(session, char_ids, location_ids=loc_filter)
    overrides = stock_assignments or {}
    price_ov = price_overrides or {}

    type_ids = {m["type_id"] for m in raw_materials}
    type_ids.add(recipe.product_type_id)
    volumes = await _volumes(session, type_ids)
    prices, pricing_source = await hub_prices_for_types(session, type_ids, hub=price_hub)

    janice_job_costs: dict[int, float | None] = {}
    if janice_configured():
        bp_ids = [int(j.get("blueprint_type_id") or 0) for j in jobs if int(j.get("blueprint_type_id") or 0) > 0]
        if bp_ids:
            janice_job_costs = await janice_base_job_costs(bp_ids)

    material_lines: list[dict[str, Any]] = []
    materials_buy_total = Decimal("0")
    materials_sell_total = Decimal("0")
    starting_stocks_buy = Decimal("0")
    starting_stocks_sell = Decimal("0")

    for mat in sorted(raw_materials, key=lambda r: r["name"].lower()):
        tid = int(mat["type_id"])
        required = int(mat["required_qty"])
        in_stock = int(stock_map.get(tid, 0))
        if tid in overrides:
            assigned = int(overrides[tid])
        elif use_max_stock:
            assigned = in_stock
        else:
            assigned = 0
        assigned = min(max(0, assigned), in_stock, required)
        to_buy = max(0, required - assigned)

        buy_p = price_ov.get(tid)
        if buy_p is None:
            buy_p = Decimal(str(prices.get(tid, {}).get("sell") or 0))
        sell_p = prices.get(tid, {}).get("buy")
        sell_p_dec = Decimal(str(sell_p)) if sell_p is not None else buy_p

        buy_val = buy_p * to_buy
        sell_val = sell_p_dec * to_buy
        materials_buy_total += buy_val
        materials_sell_total += sell_val
        starting_stocks_buy += buy_p * assigned
        starting_stocks_sell += sell_p_dec * assigned

        vol = volumes.get(tid, 0.0)
        material_lines.append(
            {
                "type_id": tid,
                "name": mat["name"],
                "required_qty": required,
                "to_buy": to_buy,
                "to_buy_buy_value": float(buy_val),
                "to_buy_sell_value": float(sell_val),
                "volume_m3": round(vol * required, 2),
                "start_amount": assigned,
                "end_amount": 0,
                "buy_unit_price": float(buy_p),
                "sell_unit_price": float(sell_p_dec),
                "in_stock": in_stock,
                "is_component": bool(mat.get("is_component")),
            }
        )

    end_qty = recipe.product_quantity * runs
    prod_prices = prices.get(recipe.product_type_id, {})
    end_buy_unit = Decimal(str(prod_prices.get("buy") or 0))
    end_sell_unit = Decimal(str(prod_prices.get("sell") or end_buy_unit * Decimal("1.05")))
    end_products_buy = end_buy_unit * end_qty
    end_products_sell = end_sell_unit * end_qty

    job_rows: list[dict[str, Any]] = []
    total_job_seconds = 0
    total_job_cost = Decimal("0")
    mat_buy_f = float(materials_buy_total)
    for job in jobs:
        secs = _apply_time_bonus(int(job["time_seconds"]), te, structure)
        bp_tid = int(job.get("blueprint_type_id") or 0)
        runs_for_job = int(job.get("runs") or runs)
        janice_cost = janice_job_costs.get(bp_tid) if bp_tid else None
        if janice_cost is not None and janice_cost > 0:
            tax = Decimal(str(structure.tax_pct or 0)) / Decimal("100")
            cost = Decimal(str(janice_cost)) * runs_for_job * (Decimal("1") + tax)
        else:
            cost = Decimal(
                str(_job_cost(mat_buy_f if job.get("is_end_product", True) else mat_buy_f * 0.3, structure))
            )
        total_job_cost += cost
        total_job_seconds += secs
        job_rows.append(
            {
                **job,
                "days": round(secs / 86400, 2),
                "job_cost": float(cost),
            }
        )

    tax_rate = sales_tax_rate if sales_tax_rate is not None else SALES_TAX_RATE
    sales_taxes = end_products_sell * tax_rate
    expected_profit = (
        end_products_sell - materials_buy_total - total_job_cost - sales_taxes
    )

    buy_list = [
        {
            "type_id": m["type_id"],
            "name": m["name"],
            "quantity": m["to_buy"],
            "unit_price": m["buy_unit_price"],
            "total_isk": m["to_buy_buy_value"],
            "volume_m3": m["volume_m3"],
        }
        for m in material_lines
        if m["to_buy"] > 0
    ]

    janice_buy_appraisal: dict[str, Any] | None = None
    if janice_configured() and buy_list:
        lines = [f"{row['name']} {row['quantity']}" for row in buy_list]
        appraisal = await janice_create_appraisal(
            "\n".join(lines),
            market=price_hub,
            pricing="buy",
            persist=True,
            comment=f"EMUMS build plan {source_name} x{runs}",
        )
        if appraisal and appraisal.get("code"):
            janice_buy_appraisal = {
                "code": appraisal["code"],
                "url": f"https://janice.e-351.com/a/{appraisal['code']}",
            }

    market_label = JANICE_MARKETS.get(price_hub.lower(), (0, price_hub))[1]

    return {
        "plan_code": secrets.token_hex(3),
        "source_type": source_type,
        "source_id": source_id,
        "source_name": source_name,
        "product_type_id": recipe.product_type_id,
        "product_name": recipe.product_name,
        "runs": runs,
        "material_mode": material_mode,
        "use_max_stock": bool(use_max_stock),
        "warehouse_container": warehouse_label,
        "warehouse_location_count": len(loc_filter) if loc_filter is not None else None,
        "price_hub": price_hub,
        "price_hub_label": market_label,
        "pricing_source": pricing_source,
        "janice_configured": janice_configured(),
        "janice_buy_appraisal": janice_buy_appraisal,
        "me": me,
        "te": te,
        "structure": {
            "structure_id": structure.structure_id,
            "structure_name": structure.structure_name,
            "system_name": structure.system_name,
            "location_label": structure.location_label,
            "material_bonus_pct": structure.material_bonus_pct,
            "time_bonus_pct": structure.time_bonus_pct,
            "tax_pct": structure.tax_pct,
        },
        "structures_available": [
            {
                "structure_id": s.structure_id,
                "structure_name": s.structure_name,
                "system_name": s.system_name,
                "location_label": s.location_label,
                "material_bonus_pct": s.material_bonus_pct,
                "time_bonus_pct": s.time_bonus_pct,
                "tax_pct": s.tax_pct,
            }
            for s in structures
        ],
        "cash_flow": {
            "starting_stocks_buy": float(starting_stocks_buy),
            "starting_stocks_sell": float(starting_stocks_sell),
            "end_stocks_buy": 0.0,
            "end_stocks_sell": 0.0,
            "materials_to_buy_buy": float(materials_buy_total),
            "materials_to_buy_sell": float(materials_sell_total),
            "manufacturing_job_costs": float(total_job_cost),
            "total_sales_taxes": float(sales_taxes),
            "invention_cost": 0.0,
            "end_products_buy": float(end_products_buy),
            "end_products_sell": float(end_products_sell),
            "expected_profit_excluding_stocks": float(expected_profit),
            "expected_profit": float(expected_profit),
        },
        "job_time": {
            "end_products_seconds": _apply_time_bonus(recipe.time_seconds * runs, te, structure),
            "total_seconds": total_job_seconds,
            "total_days": round(total_job_seconds / 86400, 2),
        },
        "materials": material_lines,
        "end_products": [
            {
                "type_id": recipe.product_type_id,
                "name": recipe.product_name,
                "amount": end_qty,
                "volume_m3": round(volumes.get(recipe.product_type_id, 0) * end_qty, 2),
                "sell_unit_price": float(end_sell_unit),
                "sell_total": float(end_products_sell),
                "buy_unit_price": float(end_buy_unit),
                "buy_total": float(end_products_buy),
            }
        ],
        "produced_parts": produced_parts,
        "jobs": job_rows,
        "buy_list": buy_list,
        "stock_available": {str(k): v for k, v in stock_map.items()},
    }
