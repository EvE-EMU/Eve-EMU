"""PI factory profitability (Adam4EVE-style rank from schematics + hub prices)."""

from __future__ import annotations

from sqlalchemy import select

from app.config import settings
from app.db.models import TypeAppraisal
from app.db.session import session_scope
from app.services.import_prices import schedule_import_price_sync
from app.services.pi_schematics import (
    PiSchematic,
    load_pi_schematics,
    pi_type_name,
)

# Default PI tax assumptions (customs + market broker).
_DEFAULT_CUSTOMS_PCT = 10.0
_DEFAULT_MARKET_PCT = 7.5

_HUB_FIELDS: dict[str, tuple[str, str]] = {
    "jita": ("jita_sell", "jita_buy"),
    "amarr": ("amarr_sell", "amarr_buy"),
    "wompstar": ("wompstar_sell", "wompstar_buy"),
}


def _price(
    appraisals: dict[int, TypeAppraisal],
    type_id: int,
    field: str,
) -> float | None:
    appr = appraisals.get(type_id)
    if not appr:
        return None
    val = getattr(appr, field, None)
    return float(val) if val is not None else None


async def _load_prices(type_ids: list[int]) -> dict[int, TypeAppraisal]:
    if not type_ids:
        return {}
    async with session_scope() as session:
        rows = (
            await session.execute(
                select(TypeAppraisal).where(TypeAppraisal.type_id.in_(type_ids))
            )
        ).scalars().all()
    return {int(a.type_id): a for a in rows}


def _calc_row(
    schematic: PiSchematic,
    *,
    appraisals: dict[int, TypeAppraisal],
    buy_field: str,
    sell_field: str,
    customs_pct: float,
    market_pct: float,
    mode: str,
) -> dict | None:
    """Factory step profit. *mode* ``factory`` (buy inputs) or ``extract`` (zero input cost)."""
    sell_p = _price(appraisals, schematic.output_type_id, sell_field)
    if sell_p is None:
        return None

    out_qty = schematic.output_quantity
    revenue = sell_p * out_qty * (1 - market_pct / 100)

    material_cost = 0.0
    missing_input = False
    input_lines: list[dict] = []

    if mode == "factory":
        for mat in schematic.inputs:
            buy_p = _price(appraisals, mat.type_id, buy_field)
            if buy_p is None:
                missing_input = True
                break
            line_cost = buy_p * mat.quantity * (1 + customs_pct / 100)
            material_cost += line_cost
            input_lines.append(
                {
                    "type_id": mat.type_id,
                    "name": pi_type_name(mat.type_id),
                    "quantity": mat.quantity,
                    "unit_price": round(buy_p, 2),
                    "line_cost": round(line_cost, 2),
                }
            )
    elif mode == "extract":
        for mat in schematic.inputs:
            input_lines.append(
                {
                    "type_id": mat.type_id,
                    "name": pi_type_name(mat.type_id),
                    "quantity": mat.quantity,
                    "unit_price": None,
                    "line_cost": 0,
                }
            )
    else:
        return None

    if mode == "factory" and missing_input:
        return None

    profit = revenue - material_cost
    hours = schematic.cycle_time / 3600.0
    profit_iph = profit / hours if hours > 0 else profit
    cost_basis = material_cost if material_cost > 0 else revenue
    profit_pct = round(100 * profit / cost_basis, 1) if cost_basis else None

    return {
        "schematic_id": schematic.schematic_id,
        "type_id": schematic.output_type_id,
        "name": pi_type_name(schematic.output_type_id),
        "schematic_name": schematic.name,
        "tier": schematic.output_tier,
        "tier_label": f"P{schematic.output_tier}",
        "mode": mode,
        "levels": 1,
        "cycle_time": schematic.cycle_time,
        "output_quantity": out_qty,
        "sell_unit": round(sell_p, 2),
        "revenue": round(revenue, 2),
        "material_cost": round(material_cost, 2),
        "profit": round(profit, 2),
        "profit_pct": profit_pct,
        "profit_iph": round(profit_iph, 2),
        "inputs": input_lines,
    }


async def pi_rank_rows(
    *,
    sale_hub: str = "jita",
    buy_from: str = "sell_orders",
    sell_to: str = "sell_orders",
    mode: str = "factory",
    tier: int | None = None,
    customs_pct: float = _DEFAULT_CUSTOMS_PCT,
    market_pct: float = _DEFAULT_MARKET_PCT,
    limit: int = 200,
) -> dict:
    hub = sale_hub.lower()
    if hub not in _HUB_FIELDS:
        hub = "jita"
    sell_key, buy_key = _HUB_FIELDS[hub]

    buy_field = sell_key if buy_from == "sell_orders" else buy_key
    sell_field = sell_key if sell_to == "sell_orders" else buy_key

    schematics = await load_pi_schematics()
    type_ids = list(
        {
            tid
            for s in schematics
            for tid in [s.output_type_id, *[m.type_id for m in s.inputs]]
        }
    )
    appraisals = await _load_prices(type_ids)

    missing = sum(
        1
        for tid in type_ids
        if tid not in appraisals
        or _price(appraisals, tid, sell_key) is None
    )
    if type_ids and missing > len(type_ids) * 0.3 and settings.wompstar_structure_id:
        schedule_import_price_sync(int(settings.wompstar_structure_id))

    rows: list[dict] = []
    for schematic in schematics:
        if tier is not None and schematic.output_tier != tier:
            continue
        row = _calc_row(
            schematic,
            appraisals=appraisals,
            buy_field=buy_field,
            sell_field=sell_field,
            customs_pct=customs_pct,
            market_pct=market_pct,
            mode=mode if mode in ("factory", "extract") else "factory",
        )
        if row:
            rows.append(row)

    rows.sort(key=lambda r: r.get("profit_iph") or 0, reverse=True)
    rows = rows[:limit]

    hub_labels = {
        "jita": "Jita 4-4",
        "amarr": "Amarr VIII",
        "wompstar": settings.wompstar_structure_name or "WOMPSTAR",
    }

    return {
        "sale_hub": hub,
        "sale_hub_label": hub_labels.get(hub, hub),
        "buy_from": buy_from,
        "sell_to": sell_to,
        "mode": mode,
        "customs_pct": customs_pct,
        "market_pct": market_pct,
        "prices_pending": missing > 0,
        "schematic_count": len(schematics),
        "rows": rows,
    }
