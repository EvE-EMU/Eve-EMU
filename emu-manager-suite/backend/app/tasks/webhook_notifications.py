"""Celery tasks for webhook notification digest delivery."""

from __future__ import annotations

import asyncio
import logging

from app.celery_app import celery_app
from app.db.session import get_session_factory
from app.services.webhook_notification_engine import flush_webhook_digests

logger = logging.getLogger(__name__)


@celery_app.task(name="app.tasks.webhook_notifications.flush_webhook_notification_digests")
def flush_webhook_notification_digests() -> dict[str, int]:
    async def _run() -> dict[str, int]:
        factory = get_session_factory()
        async with factory() as session:
            result = await flush_webhook_digests(session)
            await session.commit()
            return result

    logger.info("EMUMS: flushing webhook notification digests")
    result = asyncio.run(_run())
    logger.info("EMUMS: webhook digests complete — %s", result)
    return result
