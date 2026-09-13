"""Inventory paste parsing and Janice-backed appraisal / buyback pricing."""

from __future__ import annotations

import re
import secrets
from typing import Any

from sqlalchemy.ext.asyncio import AsyncSession

from app.config import settings
from app.services.buyback_locations import list_buyback_locations, resolve_buyback_location
from app.services.janice import (
    JANICE_MARKETS,
    janice_configured,
    janice_create_appraisal,
    janice_price_rows,
    prices_from_block,
    _price_block,
)
from app.services.sde_search import lookup_type_by_name


def _parse_qty_token(raw: str) -> int:
    cleaned = str(raw or "").replace(",", "").strip()
    if not cleaned:
        return 1
    try:
        return max(1, int(float(cleaned)))
    except ValueError:
        return 1


def _is_inventory_export_row(parts: list[str]) -> bool:
    if len(parts) < 3 or not parts[0].isdigit():
        return False
    name = parts[1].strip()
    if not name:
        return False
    try:
        float(parts[2].replace(",", ""))
    except ValueError:
        return False
    return True


def _is_qty_name_row(parts: list[str]) -> bool:
    if len(parts) != 2 or not parts[0].isdigit():
        return False
    return bool(parts[1].strip())


def parse_appraisal_text(text: str) -> list[dict[str, Any]]:
    entries: list[dict[str, Any]] = []
    for raw in (text or "").splitlines():
        line = raw.strip()
        if not line or line.startswith("#"):
            continue

        if "\t" in line:
            parts = [p.strip() for p in line.split("\t") if p.strip() != ""]
            if _is_inventory_export_row(parts):
                entries.append(
                    {
                        "query": parts[1],
                        "quantity": _parse_qty_token(parts[2]),
                        "type_id": int(parts[0]),
                    }
                )
                continue
            if _is_qty_name_row(parts):
                entries.append({"query": parts[1], "quantity": _parse_qty_token(parts[0])})
                continue
            if len(parts) >= 2 and not parts[0].isdigit():
                entries.append({"query": parts[0], "quantity": _parse_qty_token(parts[1])})
                continue

        patterns = [
            (r"^(.+?)\s+x\s*([\d,]+)\s*$", 1, 2),
            (r"^([\d,]+)\s+x\s+(.+)$", 2, 1),
        ]
        matched = False
        for pat, name_g, qty_g in patterns:
            m = re.match(pat, line, re.IGNORECASE)
            if m:
                entries.append(
                    {
                        "query": m.group(name_g).strip(),
                        "quantity": max(1, int(m.group(qty_g).replace(",", ""))),
                    }
                )
                matched = True
                break
        if not matched:
            entries.append({"query": line, "quantity": 1})
    return entries


def _lookup_price(
    janice_map: dict[str, dict],
    query: str,
    type_id: int | None,
) -> dict | None:
    if type_id is not None and str(type_id) in janice_map:
        return janice_map[str(type_id)]
    key = str(query).strip().upper()
    return janice_map.get(key)


def _prefer_reprocess_unit(*, repro_buy: float | None, market_sell: float | None) -> tuple[float | None, str]:
    """Reprocess (JBV/buy) unless raw market sell is higher — then sell unrefined."""
    if repro_buy is None and market_sell is None:
        return None, "unknown"
    if repro_buy is None:
        return market_sell, "market"
    if market_sell is None:
        return repro_buy, "reprocess"
    if market_sell > repro_buy:
        return market_sell, "market"
    return repro_buy, "reprocess"


def _lines_from_janice_appraisal(appraisal: dict[str, Any]) -> list[dict[str, Any]]:
    lines: list[dict[str, Any]] = []
    for item in appraisal.get("items") or []:
        if not isinstance(item, dict):
            continue
        prices = prices_from_block(_price_block(item))
        qty = int(item.get("amount") or 1)
        item_type = item.get("itemType") or {}
        tid = item_type.get("eid")
        name = str(item_type.get("name") or "").strip()
        lines.append(
            {
                "type_id": tid,
                "name": name,
                "quantity": qty,
                "single_buy": round(prices["buy"], 2) if prices["buy"] is not None else None,
                "single_sell": round(prices["sell"], 2) if prices["sell"] is not None else None,
                "single_split": round(prices["split"], 2) if prices["split"] is not None else None,
                "total_buy": round(prices["buy"] * qty, 2) if prices["buy"] is not None else None,
                "total_sell": round(prices["sell"] * qty, 2) if prices["sell"] is not None else None,
                "total_split": round(prices["split"] * qty, 2) if prices["split"] is not None else None,
            }
        )
    return lines


async def run_appraisal(
    *,
    text: str,
    sell_market: str = "jita",
    buy_market: str | None = None,
    session: AsyncSession | None = None,
) -> dict[str, Any]:
    """Pure Janice appraisal — buy / split / sell totals from one appraisal call."""
    buy_market = buy_market or sell_market
    entries = parse_appraisal_text(text)
    if not entries:
        return {"error": "no_items", "lines": [], "totals": {}}

    if not janice_configured():
        return {
            "error": "janice_not_configured",
            "lines": [],
            "totals": {},
            "janice_configured": False,
        }

    appraisal = await janice_create_appraisal(text, market=sell_market, pricing="split", persist=True)
    if not appraisal:
        return await _run_appraisal_fallback(
            text=text,
            entries=entries,
            sell_market=sell_market,
            buy_market=buy_market,
            session=session,
        )

    lines = _lines_from_janice_appraisal(appraisal)
    total_buy = sum(l["total_buy"] or 0 for l in lines)
    total_sell = sum(l["total_sell"] or 0 for l in lines)
    total_split = sum(l["total_split"] or 0 for l in lines)

    sell_label = JANICE_MARKETS.get(sell_market.lower(), (0, sell_market))[1]
    buy_label = JANICE_MARKETS.get(buy_market.lower(), (0, buy_market))[1]

    return {
        "sell_market": sell_market,
        "buy_market": buy_market,
        "sell_market_label": sell_label,
        "buy_market_label": buy_label,
        "janice_configured": True,
        "janice_code": appraisal.get("code"),
        "janice_url": f"https://janice.e-351.com/a/{appraisal['code']}" if appraisal.get("code") else None,
        "totals": {
            "total_sell": round(total_sell, 2),
            "total_buy": round(total_buy, 2),
            "split_value": round(total_split, 2),
        },
        "unresolved": (
            list(appraisal.get("failures") or [])
            if isinstance(appraisal.get("failures"), list)
            else ([str(appraisal["failures"])] if appraisal.get("failures") else [])
        ),
        "lines": lines,
    }


async def _run_appraisal_fallback(
    *,
    text: str,
    entries: list[dict],
    sell_market: str,
    buy_market: str,
    session: AsyncSession | None,
) -> dict[str, Any]:
    queries = [e["query"] for e in entries]
    janice_sell = await janice_price_rows(queries, market=sell_market)
    janice_buy = (
        await janice_price_rows(queries, market=buy_market) if buy_market != sell_market else janice_sell
    )

    lines: list[dict] = []
    total_sell = 0.0
    total_buy = 0.0
    total_split = 0.0
    unresolved: list[str] = []

    for entry in entries:
        query = str(entry["query"])
        qty = int(entry["quantity"])
        type_id = entry.get("type_id")
        sell_row = _lookup_price(janice_sell, query, type_id)
        buy_row = _lookup_price(janice_buy, query, type_id)

        tid = type_id
        name = query
        if sell_row:
            tid = sell_row.get("type_id") or tid
            name = sell_row.get("name") or name
        elif buy_row:
            tid = buy_row.get("type_id") or tid
            name = buy_row.get("name") or name
        elif not tid and session is not None:
            sde = await lookup_type_by_name(session, query)
            if sde:
                tid = sde["type_id"]
                name = sde["name"]

        single_sell = sell_row.get("sell") if sell_row else None
        single_buy = buy_row.get("buy") if buy_row else None
        single_split = sell_row.get("split") if sell_row else None

        if single_sell is None and single_buy is None and not tid:
            unresolved.append(query)
            continue

        ts = (single_sell or 0) * qty
        tb = (single_buy or 0) * qty
        tsp = (single_split or 0) * qty
        total_sell += ts
        total_buy += tb
        total_split += tsp

        lines.append(
            {
                "type_id": tid,
                "name": name,
                "quantity": qty,
                "single_sell": round(single_sell, 2) if single_sell is not None else None,
                "single_buy": round(single_buy, 2) if single_buy is not None else None,
                "single_split": round(single_split, 2) if single_split is not None else None,
                "total_sell": round(ts, 2) if single_sell is not None else None,
                "total_buy": round(tb, 2) if single_buy is not None else None,
                "total_split": round(tsp, 2) if single_split is not None else None,
            }
        )

    sell_label = JANICE_MARKETS.get(sell_market.lower(), (0, sell_market))[1]
    buy_label = JANICE_MARKETS.get(buy_market.lower(), (0, buy_market))[1]

    return {
        "sell_market": sell_market,
        "buy_market": buy_market,
        "sell_market_label": sell_label,
        "buy_market_label": buy_label,
        "janice_configured": janice_configured(),
        "totals": {
            "total_sell": round(total_sell, 2),
            "total_buy": round(total_buy, 2),
            "split_value": round(total_split, 2),
        },
        "unresolved": unresolved,
        "lines": lines,
    }


async def run_buyback(
    *,
    text: str,
    fee_pct: float | None = None,
    sell_market: str = "jita",
    item_location: str | None = None,
    session: AsyncSession | None = None,
    contract_code: str | None = None,
) -> dict[str, Any]:
    location = resolve_buyback_location(item_location)
    market = location.get("market") or sell_market
    fee = fee_pct if fee_pct is not None else float(location.get("fee_pct") or settings.default_buyback_fee_pct)

    entries = parse_appraisal_text(text)
    if not entries:
        return {"error": "no_items", "lines": [], "totals": {}}

    if not janice_configured():
        return {"error": "janice_not_configured", "lines": [], "totals": {}}

    sell_appraisal = await janice_create_appraisal(text, market=market, pricing="sell", persist=True)
    buy_appraisal = await janice_create_appraisal(text, market=market, pricing="buy", persist=True)

    if not sell_appraisal and not buy_appraisal:
        base = await run_appraisal(text=text, sell_market=market, session=session)
        if base.get("error"):
            return base
        basis = float(base["totals"].get("split_value") or base["totals"].get("total_sell") or 0)
        contract_value = basis * (fee / 100.0)
        code = contract_code or new_share_token()
        base.update(
            {
                "fee_pct": fee,
                "contract_value_isk": round(contract_value, 2),
                "fee_basis_isk": round(basis, 2),
                "item_location": location["id"],
                "item_location_label": location["label"],
                "contract_code": code,
                "contract_description": f"EMUMS Buyback {code}",
                "buyback_locations": list_buyback_locations(),
            }
        )
        return base

    sell_by_name: dict[str, dict] = {}
    buy_by_name: dict[str, dict] = {}
    for item in (sell_appraisal or {}).get("items") or []:
        if isinstance(item, dict):
            name = str((item.get("itemType") or {}).get("name") or "").upper()
            if name:
                sell_by_name[name] = item
    for item in (buy_appraisal or {}).get("items") or []:
        if isinstance(item, dict):
            name = str((item.get("itemType") or {}).get("name") or "").upper()
            if name:
                buy_by_name[name] = item

    lines: list[dict] = []
    basis_total = 0.0
    unresolved: list[str] = []

    for entry in entries:
        query = str(entry["query"])
        qty = int(entry["quantity"])
        key = query.upper()
        sell_item = sell_by_name.get(key)
        buy_item = buy_by_name.get(key)

        if not sell_item and not buy_item:
            unresolved.append(query)
            continue

        sell_prices = prices_from_block(_price_block(sell_item)) if sell_item else {"sell": None, "buy": None, "split": None}
        buy_prices = prices_from_block(_price_block(buy_item)) if buy_item else {"sell": None, "buy": None, "split": None}

        unit_basis, winner = _prefer_reprocess_unit(
            repro_buy=buy_prices["buy"],
            market_sell=sell_prices["sell"],
        )
        if unit_basis is None:
            unresolved.append(query)
            continue

        line_total = unit_basis * qty
        basis_total += line_total
        item_type = (sell_item or buy_item or {}).get("itemType") or {}
        lines.append(
            {
                "type_id": item_type.get("eid"),
                "name": item_type.get("name") or query,
                "quantity": qty,
                "single_sell": round(sell_prices["sell"], 2) if sell_prices["sell"] is not None else None,
                "single_buy": round(buy_prices["buy"], 2) if buy_prices["buy"] is not None else None,
                "basis_unit": round(unit_basis, 2),
                "basis_total": round(line_total, 2),
                "pricing_mode": winner,
            }
        )

    contract_value = basis_total * (fee / 100.0)
    code = contract_code or new_share_token()
    sell_label = JANICE_MARKETS.get(market.lower(), (0, market))[1]
    janice_code = (sell_appraisal or buy_appraisal or {}).get("code")

    return {
        "sell_market": market,
        "buy_market": market,
        "sell_market_label": sell_label,
        "buy_market_label": sell_label,
        "janice_configured": True,
        "janice_code": janice_code,
        "janice_url": f"https://janice.e-351.com/a/{janice_code}" if janice_code else None,
        "totals": {
            "total_sell": round(sum((l.get("single_sell") or 0) * l["quantity"] for l in lines), 2),
            "total_buy": round(sum((l.get("single_buy") or 0) * l["quantity"] for l in lines), 2),
            "split_value": round(basis_total, 2),
        },
        "unresolved": unresolved,
        "lines": lines,
        "fee_pct": fee,
        "contract_value_isk": round(contract_value, 2),
        "fee_basis_isk": round(basis_total, 2),
        "item_location": location["id"],
        "item_location_label": location["label"],
        "contract_code": code,
        "contract_description": f"EMUMS Buyback {code}",
        "buyback_locations": list_buyback_locations(),
    }


async def run_refine_compare(
    *,
    text: str,
    market: str = "jita",
    session: AsyncSession | None = None,
) -> dict[str, Any]:
    """Compare selling unrefined at hub vs Janice reprocess (JBV/buy) value per line."""
    entries = parse_appraisal_text(text)
    if not entries:
        return {"error": "no_items", "lines": [], "totals": {}}

    if not janice_configured():
        return {"error": "janice_not_configured", "lines": [], "totals": {}}

    sell_appraisal = await janice_create_appraisal(text, market=market, pricing="sell", persist=True)
    buy_appraisal = await janice_create_appraisal(text, market=market, pricing="buy", persist=True)

    if not sell_appraisal and not buy_appraisal:
        base = await run_appraisal(text=text, sell_market=market, buy_market=market, session=session)
        if base.get("error"):
            return base
        lines: list[dict[str, Any]] = []
        total_sell = 0.0
        total_refine = 0.0
        for line in base.get("lines") or []:
            sell_t = float(line.get("total_sell") or 0)
            refine_t = float(line.get("total_buy") or 0)
            winner = "sell" if sell_t > refine_t else "refine" if refine_t > sell_t else "tie"
            best = max(sell_t, refine_t)
            lines.append(
                {
                    **line,
                    "refine_total": round(refine_t, 2),
                    "sell_total": round(sell_t, 2),
                    "delta_isk": round(abs(sell_t - refine_t), 2),
                    "recommendation": winner,
                    "best_total": round(best, 2),
                }
            )
            total_sell += sell_t
            total_refine += refine_t
        winner = "sell" if total_sell > total_refine else "refine" if total_refine > total_sell else "tie"
        return {
            "sell_market": market,
            "buy_market": market,
            "sell_market_label": JANICE_MARKETS.get(market.lower(), (0, market))[1],
            "buy_market_label": JANICE_MARKETS.get(market.lower(), (0, market))[1],
            "janice_configured": True,
            "totals": {
                "total_sell": round(total_sell, 2),
                "total_refine": round(total_refine, 2),
                "delta_isk": round(abs(total_sell - total_refine), 2),
                "recommendation": winner,
            },
            "lines": lines,
            "unresolved": base.get("unresolved") or [],
        }

    sell_by_name: dict[str, dict] = {}
    buy_by_name: dict[str, dict] = {}
    for item in (sell_appraisal or {}).get("items") or []:
        if isinstance(item, dict):
            name = str((item.get("itemType") or {}).get("name") or "").upper()
            if name:
                sell_by_name[name] = item
    for item in (buy_appraisal or {}).get("items") or []:
        if isinstance(item, dict):
            name = str((item.get("itemType") or {}).get("name") or "").upper()
            if name:
                buy_by_name[name] = item

    lines = []
    total_sell = 0.0
    total_refine = 0.0
    unresolved: list[str] = []

    for entry in entries:
        query = str(entry["query"])
        qty = int(entry["quantity"])
        key = query.upper()
        sell_item = sell_by_name.get(key)
        buy_item = buy_by_name.get(key)

        if not sell_item and not buy_item:
            unresolved.append(query)
            continue

        sell_prices = prices_from_block(_price_block(sell_item)) if sell_item else {"sell": None, "buy": None}
        buy_prices = prices_from_block(_price_block(buy_item)) if buy_item else {"sell": None, "buy": None}

        unit_sell = sell_prices["sell"]
        unit_refine = buy_prices["buy"]
        sell_t = (unit_sell or 0) * qty
        refine_t = (unit_refine or 0) * qty
        if unit_sell is None and unit_refine is None:
            unresolved.append(query)
            continue

        winner = "sell" if sell_t > refine_t else "refine" if refine_t > sell_t else "tie"
        total_sell += sell_t
        total_refine += refine_t
        item_type = (sell_item or buy_item or {}).get("itemType") or {}
        lines.append(
            {
                "type_id": item_type.get("eid"),
                "name": item_type.get("name") or query,
                "quantity": qty,
                "single_sell": round(unit_sell, 2) if unit_sell is not None else None,
                "single_refine": round(unit_refine, 2) if unit_refine is not None else None,
                "sell_total": round(sell_t, 2),
                "refine_total": round(refine_t, 2),
                "delta_isk": round(abs(sell_t - refine_t), 2),
                "recommendation": winner,
                "best_total": round(max(sell_t, refine_t), 2),
            }
        )

    overall = "sell" if total_sell > total_refine else "refine" if total_refine > total_sell else "tie"
    janice_code = (sell_appraisal or buy_appraisal or {}).get("code")
    sell_label = JANICE_MARKETS.get(market.lower(), (0, market))[1]

    return {
        "sell_market": market,
        "buy_market": market,
        "sell_market_label": sell_label,
        "buy_market_label": sell_label,
        "janice_configured": True,
        "janice_code": janice_code,
        "janice_url": f"https://janice.e-351.com/a/{janice_code}" if janice_code else None,
        "totals": {
            "total_sell": round(total_sell, 2),
            "total_refine": round(total_refine, 2),
            "delta_isk": round(abs(total_sell - total_refine), 2),
            "recommendation": overall,
        },
        "unresolved": unresolved,
        "lines": lines,
    }


def new_share_token() -> str:
    return secrets.token_urlsafe(12).replace("-", "").replace("_", "")[:16]
