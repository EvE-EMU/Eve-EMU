"""Adam4EVE client for EMUMS market browser (hub prices + history, minimal ESI)."""

from __future__ import annotations

import asyncio
import logging
import time
from datetime import date, timedelta
from typing import Any

import httpx

from app.config import settings

logger = logging.getLogger(__name__)

_a4e_lock = asyncio.Lock()
_a4e_last_request = 0.0


def a4e_enabled() -> bool:
    raw = getattr(settings, "a4e_enabled", True)
    if isinstance(raw, str):
        return raw.strip().lower() in ("1", "true", "yes", "on")
    return bool(raw)


def _user_agent() -> str:
    return (
        getattr(settings, "a4e_user_agent", None)
        or "EVE-EMU-EMUMS/1.0 (+https://emums.eve-emu.com; market-browser)"
    )


def _base_url() -> str:
    return (getattr(settings, "a4e_base_url", None) or "https://api.adam4eve.eu/v1").rstrip("/")


async def acquire_a4e_slot() -> None:
    global _a4e_last_request
    interval = max(5.0, float(getattr(settings, "a4e_min_interval_seconds", 5.0)))
    async with _a4e_lock:
        now = time.monotonic()
        wait = interval - (now - _a4e_last_request)
        if wait > 0:
            await asyncio.sleep(wait)
        _a4e_last_request = time.monotonic()


def _float(value: Any) -> float | None:
    if value is None or value == "":
        return None
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def _int(value: Any) -> int:
    f = _float(value)
    return int(f) if f is not None else 0


async def _a4e_get(params: dict[str, Any], *, endpoint: str) -> Any:
    if not a4e_enabled():
        return None
    await acquire_a4e_slot()
    url = f"{_base_url()}/{endpoint.lstrip('/')}"
    try:
        async with httpx.AsyncClient(timeout=45.0) as client:
            resp = await client.get(
                url,
                params=params,
                headers={"User-Agent": _user_agent(), "Accept": "application/json"},
            )
    except httpx.HTTPError as exc:
        logger.warning("Adam4EVE %s failed: %s", endpoint, exc)
        return None
    if resp.status_code != 200:
        logger.warning("Adam4EVE %s HTTP %s: %s", endpoint, resp.status_code, resp.text[:120])
        return None
    try:
        return resp.json()
    except ValueError:
        return None


async def fetch_region_prices(
    type_id: int,
    *,
    region_id: int,
) -> dict[str, float | int | None] | None:
    body = await _a4e_get(
        {"typeID": type_id, "locationID": region_id},
        endpoint="market_prices",
    )
    if not isinstance(body, dict):
        return None
    row: dict[str, Any] | None
    if "buy_price" in body or "sell_price" in body:
        row = body
    else:
        row = body.get(str(type_id))
        if not isinstance(row, dict) and len(body) == 1:
            only = next(iter(body.values()))
            row = only if isinstance(only, dict) else None
    if not isinstance(row, dict):
        return None
    return {
        "buy": _float(row.get("buy_price")),
        "sell": _float(row.get("sell_price")),
        "buy_volume": _int(row.get("buy_volume")),
        "sell_volume": _int(row.get("sell_volume")),
        "updated": row.get("lupdate"),
    }


async def fetch_region_history(
    type_id: int,
    *,
    region_id: int,
    start: date | None = None,
    end: date | None = None,
) -> list[dict[str, Any]]:
    end_day = end or date.today()
    start_day = start or (end_day - timedelta(days=180))
    body = await _a4e_get(
        {
            "typeID": type_id,
            "regionID": region_id,
            "start": start_day.isoformat(),
            "end": end_day.isoformat(),
        },
        endpoint="market_price_history",
    )
    if not isinstance(body, list):
        return []
    rows = [r for r in body if isinstance(r, dict) and str(r.get("type_id")) == str(type_id)]
    rows.sort(key=lambda r: str(r.get("price_date") or ""))
    return rows


def history_row_to_day(row: dict[str, Any]) -> dict[str, Any] | None:
    raw_day = row.get("price_date")
    if not raw_day:
        return None
    try:
        day = date.fromisoformat(str(raw_day)[:10])
    except ValueError:
        return None
    sell_avg = _float(row.get("sell_price_avg"))
    sell_high = _float(row.get("sell_price_high"))
    sell_low = _float(row.get("sell_price_low"))
    if sell_avg is None and sell_high is None and sell_low is None:
        return None
    average = sell_avg if sell_avg is not None else (sell_high or sell_low or 0.0)
    return {
        "day": day.isoformat(),
        "average": average,
        "highest": sell_high if sell_high is not None else average,
        "lowest": sell_low if sell_low is not None else average,
        "volume": _int(row.get("sell_volume_avg")),
        "order_count": 0,
    }
