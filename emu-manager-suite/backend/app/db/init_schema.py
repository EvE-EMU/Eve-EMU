"""Seed reference data on startup (schema handled by Alembic)."""

from __future__ import annotations

import logging
from pathlib import Path

from sqlalchemy import select

from app.config import settings
from app.db.session import get_session_factory
from app.models import OrgSettings
from app.services.demo_seed import seed_demo
from app.services.desktop_backgrounds import ensure_default_desktop_backgrounds
from app.services.notifications import ensure_default_notifications
from app.services.map_layout import apply_map_layout, ensure_map_layout, layout_uses_geographic
from app.services.sde_import import ensure_sde_map, ensure_sde_types
from app.services.system_activity import refresh_activity_snapshots
from app.services.tools_seed import seed_tools

logger = logging.getLogger(__name__)


async def init_schema() -> None:
    """Load SDE, tool defaults, and optional demo data — no DDL here."""
    factory = get_session_factory()
    async with factory() as session:
        await ensure_default_desktop_backgrounds(session)
        await ensure_default_notifications(session)
        sde_path = Path(settings.sde_sqlite_path)
        if await ensure_sde_map(session, sde_path):
            logger.info("EMUMS: SDE map imported from %s", sde_path)
        if await ensure_sde_types(session, sde_path):
            logger.info("EMUMS: SDE types imported from %s", sde_path)
        if await ensure_map_layout(session):
            logger.info("EMUMS: geographic map layout computed")
        elif not await layout_uses_geographic(session):
            await apply_map_layout(session)
            logger.info("EMUMS: migrated map layout to geographic projection")
        await seed_tools(session)
        from app.services.rental_seed import ensure_rental_defaults

        await ensure_rental_defaults(session)
        from app.services.rbac import ensure_default_states

        await ensure_default_states(session)
        from app.services.storefront import ensure_storefront_defaults

        await ensure_storefront_defaults(session)
        from app.services.jump_ship_specs import ensure_jump_ships_loaded

        ensure_jump_ships_loaded(sde_path if sde_path.is_file() else None)
        try:
            snap = await refresh_activity_snapshots(session, force=True)
            if not snap.get("skipped"):
                logger.info("EMUMS: initial system activity snapshot (%s systems)", snap.get("systems", 0))
        except Exception:
            logger.exception("EMUMS: system activity snapshot failed")
        await session.commit()

    if not settings.seed_demo_data:
        return

    async with factory() as session:
        existing = await session.scalar(select(OrgSettings).limit(1))
        if existing:
            logger.info("EMUMS: schema ready (demo data already present)")
            return
        await seed_demo(session)
        await session.commit()
        logger.info("EMUMS: seeded demo dashboard data")
