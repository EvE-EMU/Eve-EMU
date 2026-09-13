"""Short-TTL cache — Redis when available, in-process fallback."""

from __future__ import annotations

import json
import logging
import time
from typing import Any

logger = logging.getLogger(__name__)

_local: dict[str, tuple[float, str]] = {}
_redis = None
_redis_checked = False


async def _redis_client():
    global _redis, _redis_checked
    if _redis_checked:
        return _redis
    _redis_checked = True
    try:
        import redis.asyncio as aioredis

        from app.config import settings

        _redis = aioredis.from_url(settings.redis_url, decode_responses=True)
        await _redis.ping()
    except Exception as exc:
        logger.debug("TTL cache: Redis unavailable (%s), using in-process fallback", exc)
        _redis = None
    return _redis


async def cache_get(key: str) -> Any | None:
    client = await _redis_client()
    if client:
        try:
            raw = await client.get(key)
            if raw is None:
                return None
            return json.loads(raw)
        except Exception:
            pass
    entry = _local.get(key)
    if not entry:
        return None
    expires, raw = entry
    if time.monotonic() > expires:
        _local.pop(key, None)
        return None
    return json.loads(raw)


async def cache_set(key: str, value: Any, *, ttl_seconds: int = 30) -> None:
    raw = json.dumps(value, default=str)
    client = await _redis_client()
    if client:
        try:
            await client.setex(key, max(1, ttl_seconds), raw)
            return
        except Exception:
            pass
    _local[key] = (time.monotonic() + ttl_seconds, raw)
    if len(_local) > 2000:
        now = time.monotonic()
        stale = [k for k, (exp, _) in _local.items() if exp <= now]
        for k in stale:
            _local.pop(k, None)


async def cache_delete_prefix(prefix: str) -> None:
    client = await _redis_client()
    if client:
        try:
            async for key in client.scan_iter(match=f"{prefix}*"):
                await client.delete(key)
        except Exception:
            pass
    drop = [k for k in _local if k.startswith(prefix)]
    for k in drop:
        _local.pop(k, None)
