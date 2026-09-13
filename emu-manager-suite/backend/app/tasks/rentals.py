"""Rental program periodic Celery tasks."""

from __future__ import annotations

import asyncio
import logging

from app.celery_app import celery_app
from app.db.session import get_session_factory
from app.services.rental_program import expire_due_leases, run_rental_jobs

logger = logging.getLogger(__name__)


async def _run_periodic_jobs_async() -> dict[str, int]:
    factory = get_session_factory()
    async with factory() as session:
        rental = await run_rental_jobs(session)
        expired = await expire_due_leases(session)
        await session.commit()
        return {**rental, "leases_expired": expired}


@celery_app.task(name="app.tasks.rentals.run_periodic_jobs", bind=True)
def run_periodic_jobs(self) -> dict[str, int]:
    """Every 30 minutes: bills, wallet poll, reminders, overdue leases."""
    logger.info("EMUMS Celery: starting rental periodic jobs (task %s)", self.request.id)
    result = asyncio.run(_run_periodic_jobs_async())
    logger.info("EMUMS Celery: rental periodic jobs complete — %s", result)
    return result
