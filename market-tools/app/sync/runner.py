"""Non-blocking structure sync for HTTP triggers."""

from __future__ import annotations

import asyncio
import logging

from app.sync.structure_orders import sync_wompstar_orders

logger = logging.getLogger(__name__)

_task: asyncio.Task | None = None


def structure_sync_running() -> bool:
    return _task is not None and not _task.done()


async def run_structure_sync_job() -> None:
    global _task
    try:
        stats = await sync_wompstar_orders()
        if stats.get("skipped"):
            logger.warning("structure sync skipped: %s", stats.get("reason"))
        elif stats.get("error"):
            logger.error("structure sync failed: %s", stats)
        else:
            logger.info("structure sync ok: %s", stats)
    except Exception:
        logger.exception("structure sync failed")
    finally:
        _task = None


def schedule_structure_sync() -> dict:
    """Start sync in background; safe to call from POST /sync/structure."""
    global _task
    if structure_sync_running():
        return {
            "status": "already_running",
            "message": "A structure sync is already in progress.",
        }
    _task = asyncio.create_task(run_structure_sync_job())
    return {
        "status": "started",
        "message": "Structure sync started (orders and names first; market groups follow in background).",
    }
