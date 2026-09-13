"""Member audit Celery tasks."""

from __future__ import annotations

import asyncio
import logging

from app.celery_app import celery_app
from app.db.session import get_session_factory
from app.services.character_roster import load_roster
from app.services.member_audit import (
    enqueue_stale_audit_syncs,
    sync_all_registered_characters,
    sync_character_audit,
)
from app.services.roster_interactions import build_roster_interactions
from app.services.universe_locations import refresh_stale_universe_locations

logger = logging.getLogger(__name__)


async def _sync_all() -> dict[str, int]:
    factory = get_session_factory()
    async with factory() as session:
        result = await sync_all_registered_characters(session)
        await session.commit()
        return result


@celery_app.task(name="app.tasks.member_audit.sync_all_characters_audit")
def sync_all_characters_audit() -> dict[str, int]:
    logger.info("EMUMS: enqueueing stale coalition member audit syncs")
    result = asyncio.run(_sync_all())
    logger.info("EMUMS: audit sync enqueue complete — %s", result)
    return result


@celery_app.task(name="app.tasks.member_audit.sync_character_audit", queue="audit")
def sync_character_audit_task(character_id: int) -> dict[str, int]:
    async def _run() -> dict[str, int]:
        factory = get_session_factory()
        async with factory() as session:
            result = await sync_character_audit(session, character_id)
            await session.commit()
            return result

    return asyncio.run(_run())


@celery_app.task(name="app.tasks.member_audit.sync_roster_alts", queue="audit")
def sync_roster_alts_task(viewer_character_id: int) -> dict:
    async def _run() -> dict:
        factory = get_session_factory()
        async with factory() as session:
            roster = await load_roster(session, viewer_character_id, use_cache=False)
            synced: list[int] = []
            skipped: list[int] = []
            errors: dict[str, str] = {}
            for row in roster:
                cid = int(row.character_id)
                if not row.token_valid:
                    skipped.append(cid)
                    continue
                try:
                    await sync_character_audit(session, cid)
                    synced.append(cid)
                except Exception as exc:
                    errors[str(cid)] = str(exc)[:200]
            await session.commit()
            return {
                "synced_count": len(synced),
                "skipped_count": len(skipped),
                "errors": errors,
                "synced": synced,
                "skipped": skipped,
            }

    return asyncio.run(_run())


@celery_app.task(name="app.tasks.member_audit.rebuild_roster_interactions", queue="audit")
def rebuild_roster_interactions_task(viewer_character_id: int) -> dict:
    async def _run() -> dict:
        from app.services.interaction_sync import sync_character_interactions

        factory = get_session_factory()
        async with factory() as session:
            roster = await load_roster(session, viewer_character_id, use_cache=False)
            rebuilt = 0
            for row in roster:
                rebuilt += await sync_character_interactions(session, int(row.character_id))
            await session.commit()
            interactions = await build_roster_interactions(
                session, viewer_character_id, limit=50
            )
            return {
                "characters": len(roster),
                "aggregate_rows": rebuilt,
                "interactions": interactions,
            }

    return asyncio.run(_run())


@celery_app.task(name="app.tasks.member_audit.refresh_universe_location_names")
def refresh_universe_location_names() -> dict[str, int]:
    async def _run() -> dict[str, int]:
        factory = get_session_factory()
        async with factory() as session:
            count = await refresh_stale_universe_locations(session)
            await session.commit()
            return {"refreshed": count}

    logger.info("EMUMS: refreshing stale universe location names")
    result = asyncio.run(_run())
    logger.info("EMUMS: universe location refresh complete — %s", result)
    return result
