"""PostgreSQL compatibility for aa-top (DB size query is MySQL-specific)."""

from __future__ import annotations

import logging

from django.db import connection

logger = logging.getLogger(__name__)


def _sql_space_used_postgresql() -> int:
    with connection.cursor() as cursor:
        cursor.execute("SELECT pg_database_size(current_database())")
        row = cursor.fetchone()
    return int(row[0] or 0)


def _open_last_aatop_txt_safe() -> str:
    import os

    from django.conf import settings

    paths = []
    if getattr(settings, "DEBUG", False) and getattr(settings, "STATICFILES_DIRS", None):
        paths.append(os.path.join(settings.STATICFILES_DIRS[0], "top", "aatop.txt"))
    paths.append(os.path.join(settings.STATIC_ROOT, "top", "aatop.txt"))

    for path in paths:
        try:
            with open(path, encoding="utf-8") as handle:
                return handle.read()
        except FileNotFoundError:
            continue
    return ""


def patch_top_for_postgresql() -> None:
    if connection.vendor != "postgresql":
        return

    import top.task_helpers as helpers

    if getattr(helpers.sql_space_used, "_eve_emu_postgres_patched", False):
        return

    helpers.open_last_aatop_txt = _open_last_aatop_txt_safe

    helpers.sql_space_used = _sql_space_used_postgresql
    helpers.sql_space_used._eve_emu_postgres_patched = True  # type: ignore[attr-defined]
    logger.debug("top_postgres_compat: patched top helpers for PostgreSQL")


def ensure_top_static_dir() -> None:
    """Create staticfiles/top/ so the first save succeeds before collectstatic."""
    import os

    from django.conf import settings

    os.makedirs(os.path.join(settings.STATIC_ROOT, "top"), exist_ok=True)
