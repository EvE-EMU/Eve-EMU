"""Moon mining / tax billing Celery tasks."""

from __future__ import annotations

import asyncio
import logging

from app.celery_app import celery_app
from app.db.session import get_session_factory
from app.services.moon_billing import generate_invoices_for_period

logger = logging.getLogger(__name__)


async def _generate_invoices_async() -> dict[str, int]:
    factory = get_session_factory()
    async with factory() as session:
        created = await generate_invoices_for_period(session)
        await session.commit()
        return {"invoices_created": created}


@celery_app.task(name="app.tasks.emu_moons.generate_invoices", bind=True)
def generate_invoices(self) -> dict[str, int]:
    """Weekly moon tax invoice generation (emu_moons queue)."""
    logger.info("EMUMS Celery: starting moon invoice generation (task %s)", self.request.id)
    result = asyncio.run(_generate_invoices_async())
    logger.info("EMUMS Celery: moon invoice generation complete — %s", result)
    return result
