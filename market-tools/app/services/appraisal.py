"""Paste-in item appraisal (Janice-style) with Janice + WOMPSTAR hub prices."""

from __future__ import annotations

import re
from typing import Any

from app.config import settings
from app.services.browser import listed_types_catalog
from app.services.janice import JANICE_MARKETS, janice_configured, janice_price_rows


def parse_appraisal_text(text: str) -> list[dict[str, Any]]:
    """Parse 'Name x Qty' / 'Qty x Name' / tab-separated inventory lines."""
    entries: list[dict[str, Any]] = []
    for raw in (text or "").splitlines():
        line = raw.strip()
        if not line or line.startswith("#"):
            continue

        if "\t" in line:
            parts = [p.strip() for p in line.split("\t") if p.strip()]
            if len(parts) >= 2:
                name = parts[0]
                qty = 1
                for part in reversed(parts[1:]):
                    cleaned = part.replace(",", "")
                    if cleaned.isdigit():
                        qty = max(1, int(cleaned))
                        break
                entries.append({"query": name, "quantity": qty})
                continue

        patterns = [
            (r"^(.+?)\s+x\s*([\d,]+)\s*$", 1, 2),
            (r"^([\d,]+)\s+x\s+(.+)$", 2, 1),
            (r"^([\d,]+)\s+(.+)$", 1, 2),
        ]
        matched = False
        for pat, name_g, qty_g in patterns:
            m = re.match(pat, line, re.IGNORECASE)
            if m:
                name = m.group(name_g).strip()
                qty = max(1, int(m.group(qty_g).replace(",", "")))
                entries.append({"query": name, "quantity": qty})
                matched = True
                break
        if not matched:
            entries.append({"query": line, "quantity": 1})
    return entries


async def _womp_prices(location_id: int) -> dict[str, dict]:
    catalog = await listed_types_catalog(location_id=location_id)
    out: dict[str, dict] = {}
    for t in catalog.get("types") or []:
        try:
            tid = int(t["type_id"])
        except (KeyError, TypeError, ValueError):
            continue
        name = str(t.get("name") or "").strip()
        row = {
            "type_id": tid,
            "name": name,
            "sell": t.get("best_sell"),
            "buy": t.get("best_buy"),
        }
        out[str(tid)] = row
        if name:
            out[name.upper()] = row
    return out


def _lookup_price(
    maps: list[dict[str, dict]],
    query: str,
    type_id: int | None,
) -> dict | None:
    for m in maps:
        if type_id is not None and str(type_id) in m:
            return m[str(type_id)]
        key = str(query).strip().upper()
        if key in m:
            return m[key]
    return None


async def run_appraisal(
    *,
    text: str,
    sell_market: str = "jita",
    buy_market: str | None = None,
    location_id: int,
    price_basis: str = "sell",
) -> dict:
    """Appraise pasted items; Janice for trade hubs, structure orders for WOMPSTAR."""
    buy_market = buy_market or sell_market
    entries = parse_appraisal_text(text)
    if not entries:
        return {"error": "no_items", "lines": []}

    queries = [e["query"] for e in entries]
    janice_sell: dict[str, dict] = {}
    janice_buy: dict[str, dict] = {}
    if janice_configured():
        janice_sell = await janice_price_rows(queries, market=sell_market)
        if buy_market != sell_market:
            janice_buy = await janice_price_rows(queries, market=buy_market)
        else:
            janice_buy = janice_sell

    womp = await _womp_prices(location_id)
    hub_name = settings.wompstar_structure_name or "WOMPSTAR"

    lines: list[dict] = []
    total_sell = 0.0
    total_buy = 0.0
    total_split = 0.0
    total_volume = 0.0
    unresolved: list[str] = []

    for entry in entries:
        query = str(entry["query"])
        qty = int(entry["quantity"])
        sell_row = _lookup_price([janice_sell], query, None)
        buy_row = _lookup_price([janice_buy], query, None)
        womp_row = _lookup_price([womp], query, sell_row.get("type_id") if sell_row else None)

        tid = None
        name = query
        vol_m3 = 0.0
        if sell_row:
            tid = sell_row["type_id"]
            name = sell_row.get("name") or name
            vol_m3 = float(sell_row.get("volume_m3") or 0)
        elif buy_row:
            tid = buy_row["type_id"]
            name = buy_row.get("name") or name
            vol_m3 = float(buy_row.get("volume_m3") or 0)
        elif womp_row:
            tid = womp_row["type_id"]
            name = womp_row.get("name") or name

        single_sell = sell_row.get("sell") if sell_row else None
        single_buy = buy_row.get("buy") if buy_row else None
        womp_sell = womp_row.get("sell") if womp_row else None
        womp_buy = womp_row.get("buy") if womp_row else None

        if single_sell is None and single_buy is None and womp_sell is None:
            unresolved.append(query)
            continue

        line_vol = vol_m3 * qty
        total_volume += line_vol
        ts = (single_sell or 0) * qty
        tb = (single_buy or 0) * qty
        total_sell += ts
        total_buy += tb
        if single_sell is not None and single_buy is not None:
            total_split += ((single_sell + single_buy) / 2) * qty
        elif single_sell is not None:
            total_split += ts
        else:
            total_split += tb

        lines.append(
            {
                "type_id": tid,
                "name": name,
                "quantity": qty,
                "single_volume_m3": round(vol_m3, 2) if vol_m3 else None,
                "total_volume_m3": round(line_vol, 2) if line_vol else None,
                "single_sell": round(single_sell, 2) if single_sell is not None else None,
                "single_buy": round(single_buy, 2) if single_buy is not None else None,
                "total_sell": round(ts, 2) if single_sell is not None else None,
                "total_buy": round(tb, 2) if single_buy is not None else None,
                "sell_isk_per_m3": round(ts / line_vol, 2) if line_vol and ts else None,
                "buy_isk_per_m3": round(tb / line_vol, 2) if line_vol and tb else None,
                "wompstar_sell": round(womp_sell, 2) if womp_sell is not None else None,
                "wompstar_buy": round(womp_buy, 2) if womp_buy is not None else None,
                "total_wompstar_sell": round(womp_sell * qty, 2)
                if womp_sell is not None
                else None,
            }
        )

    sell_label = JANICE_MARKETS.get(sell_market.lower(), (0, sell_market))[1]
    buy_label = JANICE_MARKETS.get(buy_market.lower(), (0, buy_market))[1]

    return {
        "sell_market": sell_market,
        "buy_market": buy_market,
        "sell_market_label": sell_label,
        "buy_market_label": buy_label,
        "destination_label": hub_name,
        "janice_configured": janice_configured(),
        "janice_used": janice_configured() and bool(janice_sell),
        "price_basis": price_basis,
        "totals": {
            "total_sell": round(total_sell, 2),
            "total_buy": round(total_buy, 2),
            "split_value": round(total_split, 2),
            "total_volume_m3": round(total_volume, 2),
        },
        "unresolved": unresolved,
        "lines": lines,
    }
