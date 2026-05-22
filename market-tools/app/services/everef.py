"""EVE Ref reference data (market groups, type metadata).

https://docs.everef.net/datasets/reference-data
https://everef.net/market-groups
"""

from __future__ import annotations

import asyncio
import logging
from typing import Any

import httpx

logger = logging.getLogger(__name__)

_EVEREF = "https://ref-data.everef.net"
_UA = "EVE-EMU-Market/1.0 (+https://eve-emu.com; eve-ref)"
_CONCURRENT = 16


def localized_name(value: Any) -> str:
    if isinstance(value, str):
        return value.strip()
    if isinstance(value, dict):
        for key in ("en", "de", "fr", "ja", "ru", "es", "ko", "zh"):
            v = value.get(key)
            if v:
                return str(v).strip()
        for v in value.values():
            if v:
                return str(v).strip()
    return ""


async def everef_get(path: str) -> Any:
    url = path if path.startswith("http") else f"{_EVEREF}{path}"
    async with httpx.AsyncClient(timeout=60.0) as client:
        resp = await client.get(
            url,
            headers={"Accept": "application/json", "User-Agent": _UA},
        )
    if resp.status_code != 200:
        return None
    try:
        return resp.json()
    except Exception:
        return None


async def fetch_market_group(gid: int) -> dict[str, Any] | None:
    data = await everef_get(f"/market_groups/{gid}")
    return data if isinstance(data, dict) else None


async def fetch_type_market_group_id(type_id: int) -> int | None:
    data = await everef_get(f"/types/{type_id}")
    if not isinstance(data, dict):
        return None
    mg = data.get("market_group_id")
    return int(mg) if mg is not None else None


async def fetch_all_type_ids() -> list[int]:
    data = await everef_get("/types")
    if not isinstance(data, list):
        return []
    return [int(x) for x in data]


async def fetch_type_detail(type_id: int) -> dict[str, Any] | None:
    data = await everef_get(f"/types/{type_id}")
    return data if isinstance(data, dict) else None


async def fetch_types_bulk(type_ids: list[int]) -> list[dict[str, Any]]:
    if not type_ids:
        return []
    sem = asyncio.Semaphore(_CONCURRENT)

    async def _one(tid: int) -> dict[str, Any] | None:
        async with sem:
            return await fetch_type_detail(tid)

    rows = await asyncio.gather(*[_one(tid) for tid in type_ids])
    return [r for r in rows if r is not None]


async def fetch_all_market_group_ids() -> list[int]:
    data = await everef_get("/market_groups")
    if not isinstance(data, list):
        return []
    return [int(x) for x in data]


async def fetch_market_groups_bulk(group_ids: list[int]) -> list[dict[str, Any]]:
    if not group_ids:
        return []
    sem = asyncio.Semaphore(_CONCURRENT)

    async def _one(gid: int) -> dict[str, Any] | None:
        async with sem:
            return await fetch_market_group(gid)

    rows = await asyncio.gather(*[_one(gid) for gid in group_ids])
    return [r for r in rows if r is not None]


async def fetch_type_market_groups(type_ids: list[int]) -> dict[int, int | None]:
    if not type_ids:
        return {}
    sem = asyncio.Semaphore(_CONCURRENT)

    async def _one(tid: int) -> tuple[int, int | None]:
        async with sem:
            mg = await fetch_type_market_group_id(tid)
        return tid, mg

    pairs = await asyncio.gather(*[_one(tid) for tid in type_ids])
    return dict(pairs)
