"""PostgreSQL SQL rewrites for Indy Hub raw queries (eve_sde_itemtype.published is boolean)."""

from __future__ import annotations

import logging
import re

from django.db import connection

logger = logging.getLogger(__name__)

# MySQL-style published checks on a boolean column break on PostgreSQL.
_PUBLISHED_REWRITES: tuple[tuple[re.Pattern[str], str], ...] = (
    (
        re.compile(
            r"COALESCE\((?P<col>[a-zA-Z_][\w.]*\.published|published),\s*0\)\s*=\s*1",
            re.IGNORECASE,
        ),
        r"\g<col> IS TRUE",
    ),
    (
        re.compile(
            r"COALESCE\((?P<col>[a-zA-Z_][\w.]*\.published|published),\s*0\)\s*=\s*0",
            re.IGNORECASE,
        ),
        r"(\g<col> IS NOT TRUE)",
    ),
    (
        re.compile(
            r"(?P<col>[a-zA-Z_][\w.]*\.published|published)\s*=\s*1(?!\d)",
            re.IGNORECASE,
        ),
        r"\g<col> IS TRUE",
    ),
    (
        re.compile(
            r"(?P<col>[a-zA-Z_][\w.]*\.published|published)\s*=\s*0(?!\d)",
            re.IGNORECASE,
        ),
        r"\g<col> IS NOT TRUE",
    ),
)


def rewrite_indy_hub_sql(sql: str) -> str:
    if connection.vendor != "postgresql" or not isinstance(sql, str):
        return sql
    out = sql
    for pattern, replacement in _PUBLISHED_REWRITES:
        out = pattern.sub(replacement, out)
    return out


def patch_indy_hub_for_postgresql() -> None:
    if connection.vendor != "postgresql":
        return

    from django.db.backends.utils import CursorWrapper

    if getattr(CursorWrapper.execute, "_indy_hub_postgres_patched", False):
        return

    _original_execute = CursorWrapper.execute
    _original_executemany = CursorWrapper.executemany

    def execute(self, sql, params=None):  # noqa: ANN001
        if isinstance(sql, str):
            sql = rewrite_indy_hub_sql(sql)
        return _original_execute(self, sql, params)

    def executemany(self, sql, param_list):  # noqa: ANN001
        if isinstance(sql, str):
            sql = rewrite_indy_hub_sql(sql)
        return _original_executemany(self, sql, param_list)

    execute._indy_hub_postgres_patched = True  # type: ignore[attr-defined]
    executemany._indy_hub_postgres_patched = True  # type: ignore[attr-defined]
    CursorWrapper.execute = execute
    CursorWrapper.executemany = executemany
    logger.debug("indy_hub_postgres_compat: patched CursorWrapper for published SQL")
