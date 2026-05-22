"""Janice API client (Jita / Amarr / other trade hubs)."""

from __future__ import annotations

import logging
import os
from typing import Any

import httpx

from app.config import settings

logger = logging.getLogger(__name__)

_JANICE_BASE = "https://janice.e-351.com/api/rest/v2"
_UA = "EVE-EMU-Market/1.0 (+https://eve-emu.com; janice)"

# https://github.com/E-351/janice/blob/master/janice-v2.gs
JANICE_MARKETS: dict[str, tuple[int, str]] = {
    "jita": (2, "Jita 4-4"),
    "amarr": (115, "Amarr VIII"),
    "rens": (116, "Rens"),
    "dodixie": (117, "Dodixie"),
    "hek": (118, "Hek"),
}


def janice_api_key() -> str:
    key = (settings.janice_api_key or "").strip()
    if key:
        return key
    return (os.environ.get("BUYBACKPROGRAM_PRICE_JANICE_API_KEY") or "").strip()


def janice_configured() -> bool:
    return bool(janice_api_key())


async def janice_validate_key() -> bool:
    key = janice_api_key()
    if not key:
        return False
    try:
        async with httpx.AsyncClient(timeout=20.0) as client:
            resp = await client.get(
                f"{_JANICE_BASE}/markets",
                headers={"X-ApiKey": key, "accept": "application/json"},
            )
        if resp.status_code != 200:
            return False
        body = resp.json()
        return not (isinstance(body, dict) and body.get("status"))
    except Exception:
        logger.exception("janice key validation failed")
        return False


def _price_fields(row: dict[str, Any]) -> tuple[float | None, float | None]:
    if settings.janice_instant_prices:
        block = row.get("immediatePrices") or {}
    else:
        block = row.get("top5AveragePrices") or {}
    try:
        sell = float(block.get("sellPrice5DayMedian"))
    except (TypeError, ValueError):
        sell = None
    try:
        buy = float(block.get("buyPrice5DayMedian"))
    except (TypeError, ValueError):
        buy = None
    return sell, buy


async def janice_price_rows(
    queries: list[str | int],
    *,
    market: str = "jita",
    chunk_size: int = 80,
) -> dict[str, dict]:
    """POST item names/ids to Janice pricer; keyed by uppercased name and type id string."""
    key = janice_api_key()
    if not key or not queries:
        return {}

    market_key = (market or "jita").lower()
    if market_key not in JANICE_MARKETS:
        market_key = "jita"
    market_id, _ = JANICE_MARKETS[market_key]

    out: dict[str, dict] = {}
    headers = {
        "X-ApiKey": key,
        "Content-Type": "text/plain",
        "accept": "application/json",
        "User-Agent": _UA,
    }

    async with httpx.AsyncClient(timeout=60.0) as client:
        for i in range(0, len(queries), chunk_size):
            chunk = queries[i : i + chunk_size]
            payload = "\n".join(str(q).strip() for q in chunk if str(q).strip())
            if not payload:
                continue
            try:
                resp = await client.post(
                    f"{_JANICE_BASE}/pricer",
                    params={"market": market_id},
                    content=payload,
                    headers=headers,
                )
            except Exception:
                logger.exception("janice pricer request failed market=%s", market_key)
                continue
            if resp.status_code != 200:
                logger.warning("janice pricer %s: %s", resp.status_code, resp.text[:200])
                continue
            data = resp.json()
            if not isinstance(data, list):
                continue
            for row in data:
                if not isinstance(row, dict):
                    continue
                item = row.get("itemType") or {}
                try:
                    tid = int(item.get("eid"))
                except (TypeError, ValueError):
                    continue
                name = str(item.get("name") or "").strip()
                sell, buy = _price_fields(row)
                try:
                    vol = float(item.get("volume") or 0)
                except (TypeError, ValueError):
                    vol = 0.0
                parsed = {
                    "type_id": tid,
                    "name": name,
                    "sell": sell,
                    "buy": buy,
                    "volume_m3": vol,
                    "market_id": market_id,
                    "market_key": market_key,
                }
                out[str(tid)] = parsed
                if name:
                    out[name.upper()] = parsed

    return out


async def janice_prices_by_type_id(
    type_ids: list[int],
    *,
    market: str = "jita",
) -> dict[int, dict]:
    """Batch Janice prices for numeric type IDs."""
    if not type_ids:
        return {}
    rows = await janice_price_rows(type_ids, market=market)
    out: dict[int, dict] = {}
    for tid in type_ids:
        hit = rows.get(str(tid))
        if hit:
            out[tid] = hit
    return out
