"""Janice-backed pricing helpers and per-line variant selection."""

from __future__ import annotations

import statistics
from typing import Any

from buybackprogram.app_settings import (
    BUYBACKPROGRAM_PRICE_INSTANT_PRICES,
    BUYBACKPROGRAM_PRICE_JANICE_API_KEY,
    BUYBACKPROGRAM_PRICE_METHOD,
)
from buybackprogram.tasks import valid_janice_api_key
from django.utils import timezone
from eveuniverse.models import EveTypeMaterial

from buyback_v2.context import get_pricing_context
from buyback_v2.models import PriceBasis, ProgramPricingProfile, VariantSelection


def _safe_float(value: Any) -> float:
    try:
        if value is None or value is False:
            return 0.0
        return float(value)
    except (TypeError, ValueError):
        return 0.0


def _variant_value(block: dict | bool | None) -> float:
    if not block or not isinstance(block, dict):
        return 0.0
    return _safe_float(block.get("value"))


def effective_price_basis(profile: ProgramPricingProfile, program) -> str:
    if profile.price_basis == PriceBasis.PROGRAM:
        return str(program.price_type or "Buy")
    if profile.price_basis == PriceBasis.BUY:
        return "Buy"
    if profile.price_basis == PriceBasis.SELL:
        return "Sell"
    return "Split"


def apply_jita_percent(value: float, profile: ProgramPricingProfile) -> float:
    if value <= 0:
        return 0.0
    return value * (profile.jita_buy_percent / 100.0)


def select_line_buy_value(
    *,
    raw_item: dict,
    refined: dict,
    compressed: dict | bool,
    profile: ProgramPricingProfile,
    program,
) -> tuple[float, float, float, str]:
    """
    Returns (buy_value, raw_value, unit_value, winner_key).
    winner_key is one of: raw, refined, compressed, npc.
    """
    market_val = _variant_value(raw_item)
    repro_val = _variant_value(refined)
    comp_val = _variant_value(compressed) if profile.include_compressed else 0.0

    mode = profile.variant_selection

    if mode == VariantSelection.LEGACY_MAX:
        buy_value = max(market_val, repro_val, comp_val)
    elif mode == VariantSelection.MARKET_ONLY:
        buy_value = market_val
    elif mode == VariantSelection.REPROCESS_ONLY:
        buy_value = repro_val
    elif mode == VariantSelection.CORP_MIN:
        if repro_val and market_val:
            buy_value = min(repro_val, market_val)
        else:
            buy_value = repro_val or market_val
        if profile.include_compressed and comp_val:
            buy_value = min(buy_value, comp_val) if buy_value else comp_val
    else:
        # PREFER_REPROCESS: reprocess unless unrefined market is cheaper (per line).
        if repro_val and market_val:
            buy_value = market_val if market_val < repro_val else repro_val
        else:
            buy_value = repro_val or market_val
        if profile.include_compressed and comp_val:
            buy_value = max(buy_value, comp_val)

    raw_value = max(
        _safe_float(raw_item.get("raw_value")),
        _safe_float(refined.get("raw_value") if isinstance(refined, dict) else 0),
        _safe_float(compressed.get("raw_value") if isinstance(compressed, dict) else 0),
    )
    unit_value = max(
        _safe_float(raw_item.get("unit_value")),
        _safe_float(refined.get("unit_value") if isinstance(refined, dict) else 0),
        _safe_float(compressed.get("unit_value") if isinstance(compressed, dict) else 0),
    )

    buy_value = apply_jita_percent(buy_value, profile)

    winner = "raw"
    if buy_value == apply_jita_percent(repro_val, profile) and repro_val:
        winner = "refined"
    elif buy_value == apply_jita_percent(comp_val, profile) and comp_val:
        winner = "compressed"
    elif buy_value == apply_jita_percent(market_val, profile) and market_val:
        winner = "raw"

    return buy_value, raw_value, unit_value, winner


def recompute_item_values(
    values: dict,
    item_prices: dict,
    program,
    profile: ProgramPricingProfile,
) -> dict:
    """Replace buy_value selection after stock buybackprogram.helpers.get_item_values()."""
    if item_prices.get("npc_prices"):
        return values

    raw_item = values["normal"]
    refined = values["refined"]
    compressed = values["compressed"]

    buy_value, raw_value, unit_value, winner = select_line_buy_value(
        raw_item=raw_item,
        refined=refined,
        compressed=compressed,
        profile=profile,
        program=program,
    )

    for key in ("normal", "refined", "compressed"):
        block = values.get(key)
        if isinstance(block, dict):
            block["is_buy_value"] = False

    winner_block = values.get(winner if winner != "raw" else "normal")
    if isinstance(winner_block, dict):
        winner_block["is_buy_value"] = True
        tax_value = winner_block.get("total_tax")
    else:
        tax_value = raw_item.get("total_tax")

    values["buy_value"] = buy_value
    values["raw_value"] = raw_value
    values["unit_value"] = unit_value
    values["tax_value"] = tax_value
    values["v2_winner"] = winner
    values["v2_price_basis"] = effective_price_basis(profile, program)
    return apply_tier_multiplier(values)


def apply_tier_multiplier(values: dict) -> dict:
    ctx = get_pricing_context()
    if not ctx or ctx.multiplier == 1.0:
        return values

    mult = float(ctx.multiplier)
    base = _safe_float(values.get("buy_value"))
    values["buy_value_base"] = base
    values["buy_value"] = base * mult
    values["v2_tier_multiplier"] = mult
    values["v2_tier_name"] = ctx.tier_name
    values["v2_tier_public"] = ctx.is_public
    return values


def item_has_refining_materials(eve_type_id: int) -> bool:
    return EveTypeMaterial.objects.filter(eve_type_id=eve_type_id).exists()


def ensure_material_prices(item_type, name: str, quantity: int, program, prices: dict) -> dict:
    """Add material_prices for non-ore items when v2 reprocess-all is enabled."""
    if prices.get("material_prices"):
        return prices
    if not item_has_refining_materials(item_type.id):
        return prices

    from buybackprogram.helpers import get_or_create_prices

    item_material_price = []
    type_materials = EveTypeMaterial.objects.filter(eve_type_id=item_type.id).prefetch_related(
        "eve_type"
    )
    for material in type_materials:
        material_price = get_or_create_prices(material.material_eve_type.id)
        material_quantity = (material.quantity * quantity) / item_type.portion_size
        item_material_price.append(
            {
                "id": material.material_eve_type.id,
                "quantity": material_quantity,
                "unit_quantity": material.quantity / item_type.portion_size,
                "buy": material_price.buy,
                "sell": material_price.sell,
            }
        )

    prices["material_prices"] = item_material_price
    prices["has_price_variants"] = True
    return prices


def fetch_janice_price_row(eve_type_id: int) -> dict[str, float] | None:
    if BUYBACKPROGRAM_PRICE_METHOD != "Janice" or not valid_janice_api_key():
        return None

    import requests

    response = requests.get(
        f"https://janice.e-351.com/api/rest/v2/pricer/{eve_type_id}",
        headers={
            "Content-Type": "text/plain",
            "X-ApiKey": BUYBACKPROGRAM_PRICE_JANICE_API_KEY,
            "accept": "application/json",
        },
        timeout=30,
    )
    if response.status_code != 200:
        return None

    item = response.json()
    if BUYBACKPROGRAM_PRICE_INSTANT_PRICES:
        buy = float(item["immediatePrices"]["buyPrice5DayMedian"])
        sell = float(item["immediatePrices"]["sellPrice5DayMedian"])
    else:
        buy = float(item["top5AveragePrices"]["buyPrice5DayMedian"])
        sell = float(item["top5AveragePrices"]["sellPrice5DayMedian"])
    return {"buy": buy, "sell": sell}


def ensure_janice_item_price(eve_type_id: int, *, force: bool) -> None:
    if not force or BUYBACKPROGRAM_PRICE_METHOD != "Janice":
        return

    from buybackprogram.models import ItemPrices

    row = ItemPrices.objects.filter(eve_type_id=eve_type_id).first()
    if row and row.buy and row.sell:
        updated = timezone.now() - row.updated
        if updated.total_seconds() < 3600:
            return

    prices = fetch_janice_price_row(eve_type_id)
    if not prices:
        return

    ItemPrices.objects.update_or_create(
        eve_type_id=eve_type_id,
        defaults={
            "buy": prices["buy"],
            "sell": prices["sell"],
            "updated": timezone.now(),
        },
    )


def price_from_basis(*, buy: float, sell: float, basis: str) -> float:
    if basis == "Sell":
        return sell
    if basis == "Split":
        return statistics.median([sell, buy])
    return buy
