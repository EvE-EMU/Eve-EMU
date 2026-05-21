"""Redis-backed ESI pacing (respect error-limit headers when present)."""

from __future__ import annotations

import asyncio
import time

import redis.asyncio as aioredis

from app.config import settings

_redis_client: aioredis.Redis | None = None
_local_lock = asyncio.Lock()
_last_request = 0.0


async def get_redis() -> aioredis.Redis | None:
    global _redis_client
    if _redis_client is not None:
        return _redis_client
    try:
        _redis_client = aioredis.from_url(settings.redis_url, decode_responses=True)
        await _redis_client.ping()
        return _redis_client
    except Exception:
        _redis_client = None
        return None


async def acquire_slot() -> None:
    """Wait until the next ESI request slot is available."""
    global _last_request
    interval = max(0.05, float(settings.esi_min_interval_seconds))
    r = await get_redis()
    if r is not None:
        key = "market:esi:next"
        while True:
            now = time.monotonic()
            pipe = r.pipeline()
            pipe.get(key)
            raw = await pipe.execute()
            next_at = float(raw[0] or 0)
            if now >= next_at:
                await r.set(key, str(now + interval), ex=120)
                return
            await asyncio.sleep(min(0.25, next_at - now))
    async with _local_lock:
        now = time.monotonic()
        wait = interval - (now - _last_request)
        if wait > 0:
            await asyncio.sleep(wait)
        _last_request = time.monotonic()


async def note_error_limit(*, remain: int | None, reset: int | None) -> None:
    if remain is None or remain > 5:
        return
    delay = float(reset or 60)
    r = await get_redis()
    if r is not None:
        await r.set("market:esi:next", str(time.monotonic() + delay), ex=int(delay) + 30)
