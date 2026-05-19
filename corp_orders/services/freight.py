from __future__ import annotations

from decimal import Decimal
from typing import Any

import requests

from corp_orders.constants import NITROGEN_ISOTOPES_TYPE_ID
from corp_orders.models import FreightOrdersSettings
from corp_orders.services.pricing import janice_sell_price


def fetch_pushx_quote(
    *,
    origin: str,
    destination: str,
    volume_m3: float,
    collateral_isk: int,
    api_client: str,
) -> dict[str, Any]:
    response = requests.get(
        "https://api.pushx.net/api/quote/JSON/",
        params={
            "startSystemName": origin,
            "endSystemName": destination,
            "volume": max(0.01, volume_m3),
            "collateral": max(0, collateral_isk),
            "apiClient": api_client or "eve-emu",
        },
        timeout=20,
    )
    response.raise_for_status()
    data = response.json()
    if data.get("PriceError") or data.get("GeneralError"):
        raise ValueError(data.get("PriceError") or data.get("GeneralError"))
    return data


def calculate_freight_isk(
    *,
    config: FreightOrdersSettings,
    volume_m3: Decimal,
    items_subtotal_isk: int,
    sell_prices: dict[int, Decimal] | None = None,
) -> tuple[int, dict[str, Any]]:
    """
    PushX Jita → destination. Above threshold: split PushX vs Rhea N2 fuel cost, capped at PushX.
    """
    volume_f = float(volume_m3)
    collateral = max(items_subtotal_isk, 1)
    pushx = fetch_pushx_quote(
        origin=config.origin_system,
        destination=config.destination_system,
        volume_m3=volume_f,
        collateral_isk=collateral,
        api_client=config.pushx_api_client,
    )
    pushx_normal = int(pushx.get("PriceNormal") or 0)
    pushx_rush = int(pushx.get("PriceRush") or 0)
    threshold = int(config.freight_volume_threshold_m3)

    detail: dict[str, Any] = {
        "pushx_normal_isk": pushx_normal,
        "pushx_rush_isk": pushx_rush,
        "pushx_route": pushx.get("RouteInfo"),
        "volume_m3": str(volume_m3),
        "threshold_m3": threshold,
        "method": "pushx",
    }

    if volume_m3 <= threshold:
        detail["note"] = "Volume at or below threshold — PushX quote used."
        return pushx_normal, detail

    sell = (sell_prices or {}).get(NITROGEN_ISOTOPES_TYPE_ID)
    if sell is None:
        sell = janice_sell_price(NITROGEN_ISOTOPES_TYPE_ID)
    if sell is None:
        detail["method"] = "pushx_fallback"
        detail["note"] = "Janice unavailable for N2 isotopes — using PushX only."
        return pushx_normal, detail

    isotope_cost = int(
        (sell * Decimal(config.rhea_nitrogen_isotopes)).quantize(Decimal("1"))
    )
    split = int((pushx_normal + isotope_cost) / 2)
    freight = min(pushx_normal, split)
    detail.update(
        {
            "method": "pushx_rhea_split",
            "nitrogen_isotopes_qty": config.rhea_nitrogen_isotopes,
            "nitrogen_jita_sell_unit": str(sell),
            "nitrogen_total_isk": isotope_cost,
            "split_average_isk": split,
            "note": "Volume above threshold — average of PushX and Rhea N2 fuel, capped at PushX.",
        }
    )
    return freight, detail
