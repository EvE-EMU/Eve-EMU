"""Janice API client for trade hub pricing and appraisals."""

from __future__ import annotations

import logging
import os
from typing import Any

import httpx

from app.config import settings

logger = logging.getLogger(__name__)

_JANICE_BASE = "https://janice.e-351.com/api/rest/v2"
_UA = "EVE-EMU-EMUMS/1.0 (+https://emums.eve-emu.com; janice)"

JANICE_MARKETS: dict[str, tuple[int, str]] = {
    "jita": (2, "Jita 4-4"),
    "amarr": (115, "Amarr VIII"),
    "rens": (116, "Rens"),
    "dodixie": (117, "Dodixie"),
    "hek": (118, "Hek"),
}


def janice_api_key() -> str:
    for candidate in (
        settings.janice_api_key,
        os.environ.get("EMUMS_JANICE_API_KEY"),
        os.environ.get("MARKET_JANICE_API_KEY"),
        os.environ.get("BUYBACKPROGRAM_PRICE_JANICE_API_KEY"),
    ):
        key = (candidate or "").strip()
        if key:
            return key
    return ""


def janice_configured() -> bool:
    return bool(janice_api_key())


def market_id_for(slug: str) -> int:
    return JANICE_MARKETS.get(slug.lower(), JANICE_MARKETS["jita"])[0]


def _price_block(row: dict[str, Any]) -> dict[str, Any]:
    if settings.janice_instant_prices:
        block = row.get("immediatePrices")
        if isinstance(block, dict):
            return block
    block = row.get("top5AveragePrices")
    if isinstance(block, dict):
        return block
    block = row.get("effectivePrices")
    return block if isinstance(block, dict) else {}


def _float_or_none(value: Any) -> float | None:
    try:
        if value is None:
            return None
        return float(value)
    except (TypeError, ValueError):
        return None


def prices_from_block(block: dict[str, Any]) -> dict[str, float | None]:
    buy = _float_or_none(block.get("buyPrice5DayMedian")) or _float_or_none(block.get("buyPrice"))
    sell = _float_or_none(block.get("sellPrice5DayMedian")) or _float_or_none(block.get("sellPrice"))
    split = _float_or_none(block.get("splitPrice5DayMedian")) or _float_or_none(block.get("splitPrice"))
    return {"buy": buy, "sell": sell, "split": split}


def _item_prices(row: dict[str, Any]) -> dict[str, float | None]:
    return prices_from_block(_price_block(row))


async def janice_price_rows(
    queries: list[str | int],
    *,
    market: str = "jita",
    chunk_size: int = 80,
) -> dict[str, dict]:
    """Batch pricer lookup — keyed by type id string and uppercased name."""
    key = janice_api_key()
    if not key:
        return {}

    market_id = market_id_for(market)
    out: dict[str, dict] = {}
    payload_lines = [str(q).strip() for q in queries if str(q).strip()]

    async with httpx.AsyncClient(timeout=30.0) as client:
        for i in range(0, len(payload_lines), chunk_size):
            chunk = payload_lines[i : i + chunk_size]
            body_text = "\n".join(chunk)
            try:
                resp = await client.post(
                    f"{_JANICE_BASE}/pricer",
                    params={"market": market_id},
                    headers={
                        "X-ApiKey": key,
                        "accept": "application/json",
                        "Content-Type": "text/plain",
                        "User-Agent": _UA,
                    },
                    content=body_text,
                )
                if resp.status_code != 200:
                    logger.warning("janice pricer %s: %s", resp.status_code, resp.text[:200])
                    continue
                body = resp.json()
                for row in body if isinstance(body, list) else body.get("items", []):
                    if not isinstance(row, dict):
                        continue
                    prices = _item_prices(row)
                    item = row.get("itemType") or row.get("item") or {}
                    tid = item.get("eid") or item.get("id") or item.get("typeId")
                    name = str(item.get("name") or "").strip()
                    entry = {
                        "type_id": tid,
                        "name": name,
                        "sell": prices["sell"],
                        "buy": prices["buy"],
                        "split": prices["split"],
                        "volume_m3": item.get("volume"),
                    }
                    if tid is not None:
                        out[str(tid)] = entry
                    if name:
                        out[name.upper()] = entry
            except Exception:
                logger.exception("janice pricer chunk failed")
    return out


async def janice_create_appraisal(
    text: str,
    *,
    market: str = "jita",
    pricing: str = "split",
    persist: bool = True,
    comment: str | None = None,
) -> dict[str, Any] | None:
    """Create a Janice appraisal from raw paste text."""
    key = janice_api_key()
    if not key or not (text or "").strip():
        return None

    market_id = market_id_for(market)
    params: dict[str, Any] = {
        "market": market_id,
        "pricing": pricing,
        "persist": persist,
        "compactize": True,
    }
    if comment:
        params["comment"] = comment[:500]

    async with httpx.AsyncClient(timeout=45.0) as client:
        resp = await client.post(
            f"{_JANICE_BASE}/appraisal",
            params=params,
            headers={
                "X-ApiKey": key,
                "accept": "application/json",
                "Content-Type": "text/plain",
                "User-Agent": _UA,
            },
            content=text.strip(),
        )
    if resp.status_code != 200:
        logger.warning("janice appraisal %s: %s", resp.status_code, resp.text[:300])
        return None
    body = resp.json()
    return body if isinstance(body, dict) else None


async def janice_prices_by_type_id(
    type_ids: list[int],
    *,
    market: str = "jita",
) -> dict[int, dict]:
    """Batch Janice prices keyed by type id."""
    if not type_ids:
        return {}
    rows = await janice_price_rows(type_ids, market=market)
    out: dict[int, dict] = {}
    for tid in type_ids:
        hit = rows.get(str(tid))
        if hit:
            out[tid] = hit
    return out


async def janice_base_job_costs(
    blueprint_type_ids: list[int],
    *,
    activity: str = "manufacturing",
) -> dict[int, float | None]:
    """Janice industry API — base job cost per blueprint type id."""
    key = janice_api_key()
    if not key or not blueprint_type_ids:
        return {}

    body_text = "\n".join(str(int(tid)) for tid in blueprint_type_ids if int(tid) > 0)
    out: dict[int, float | None] = {}
    async with httpx.AsyncClient(timeout=30.0) as client:
        try:
            resp = await client.post(
                f"{_JANICE_BASE}/industry/base-job-cost",
                params={"activity": activity},
                headers={
                    "X-ApiKey": key,
                    "accept": "application/json",
                    "Content-Type": "text/plain",
                    "User-Agent": _UA,
                },
                content=body_text,
            )
            if resp.status_code != 200:
                logger.warning("janice base-job-cost %s: %s", resp.status_code, resp.text[:200])
                return out
            payload = resp.json()
            rows = payload if isinstance(payload, list) else []
            for row in rows:
                if not isinstance(row, dict):
                    continue
                item = row.get("itemType") or {}
                tid = item.get("eid") or item.get("id") or item.get("typeId")
                if tid is None:
                    continue
                out[int(tid)] = _float_or_none(row.get("baseJobCost"))
        except Exception:
            logger.exception("janice base-job-cost failed")
    return out


async def janice_validate_key() -> bool:
    key = janice_api_key()
    if not key:
        return False
    async with httpx.AsyncClient(timeout=15.0) as client:
        try:
            resp = await client.get(
                f"{_JANICE_BASE}/markets",
                headers={"X-ApiKey": key, "accept": "application/json", "User-Agent": _UA},
            )
            return resp.status_code == 200
        except Exception:
            logger.exception("janice key validation failed")
            return False


async def janice_get_appraisal(code: str) -> dict[str, Any] | None:
    key = janice_api_key()
    if not key or not code:
        return None
    async with httpx.AsyncClient(timeout=30.0) as client:
        resp = await client.get(
            f"{_JANICE_BASE}/appraisal/{code}",
            headers={"X-ApiKey": key, "accept": "application/json", "User-Agent": _UA},
        )
    if resp.status_code != 200:
        return None
    body = resp.json()
    return body if isinstance(body, dict) else None
