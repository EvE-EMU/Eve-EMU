"""External service sync Celery tasks."""

from __future__ import annotations

import asyncio
import logging

from app.celery_app import celery_app
from app.db.session import get_session_factory
from app.services.service_sync import sync_user_services

logger = logging.getLogger(__name__)


@celery_app.task(name="app.tasks.service_sync.sync_user_services_task")
def sync_user_services_task(character_id: int) -> dict:
    async def _run() -> dict:
        factory = get_session_factory()
        async with factory() as session:
            result = await sync_user_services(session, character_id)
            await session.commit()
            return result

    logger.info("EMUMS: syncing external services for character %s", character_id)
    return asyncio.run(_run())
