"""Direct Wiki.js Postgres helpers (bulk import / purge)."""

from __future__ import annotations

import hashlib
import json
import os
import threading
from datetime import datetime, timezone

from psycopg2.extras import execute_values

LOCALE = "en"
EDITOR = "markdown"
CONTENT_TYPE = "markdown"


def _connect():
    import psycopg2

    return psycopg2.connect(
        host=os.environ.get("POSTGRES_HOST", "db"),
        port=os.environ.get("POSTGRES_PORT", "5432"),
        user=os.environ["POSTGRES_USER"],
        password=os.environ["POSTGRES_PASSWORD"],
        dbname=os.environ.get("POSTGRES_DB_WIKI", "wikijs"),
    )


def _utc_now_iso() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%S.%f")[:-3] + "Z"


def page_content_hash(path: str, content: str) -> str:
    """Stable revision hash (Wiki.js accepts any unique hex; this is deterministic)."""
    return hashlib.sha1(f"{path.strip('/')}\0{content}".encode("utf-8")).hexdigest()


def count_pages_under_prefix(prefix: str) -> int:
    prefix = prefix.strip("/")
    with _connect() as conn:
        with conn.cursor() as cur:
            cur.execute(
                'SELECT COUNT(*) FROM pages WHERE path = %s OR path LIKE %s',
                (prefix, f"{prefix}/%"),
            )
            return int(cur.fetchone()[0])


def repair_bulk_imported_pages(prefix: str = "sde") -> int:
    """Fix NULL columns that break Wiki.js render on DB-imported pages."""
    prefix = prefix.strip("/")
    with _connect() as conn:
        with conn.cursor() as cur:
            cur.execute(
                """
                UPDATE pages
                SET "privateNS" = COALESCE("privateNS", ''),
                    "publishStartDate" = COALESCE("publishStartDate", ''),
                    "publishEndDate" = COALESCE("publishEndDate", ''),
                    toc = COALESCE(toc, '[]'::json)
                WHERE path = %s OR path LIKE %s
                """,
                (prefix, f"{prefix}/%"),
            )
            fixed = cur.rowcount
        conn.commit()
    return fixed


def iter_unrendered_page_ids(prefix: str = "sde"):
    prefix = prefix.strip("/")
    with _connect() as conn:
        with conn.cursor(name="sde_unrendered") as cur:
            cur.itersize = 2000
            cur.execute(
                """
                SELECT id FROM pages
                WHERE (path = %s OR path LIKE %s)
                  AND (render IS NULL OR render = '')
                ORDER BY id
                """,
                (prefix, f"{prefix}/%"),
            )
            for (page_id,) in cur:
                yield int(page_id)


def count_unrendered_pages(prefix: str = "sde") -> int:
    prefix = prefix.strip("/")
    with _connect() as conn:
        with conn.cursor() as cur:
            cur.execute(
                """
                SELECT COUNT(*) FROM pages
                WHERE (path = %s OR path LIKE %s)
                  AND (render IS NULL OR render = '')
                """,
                (prefix, f"{prefix}/%"),
            )
            return int(cur.fetchone()[0])


def purge_pages_via_db(prefix: str) -> int:
    """Delete all Wiki.js pages under prefix directly in Postgres."""
    prefix = prefix.strip("/")
    with _connect() as conn:
        with conn.cursor() as cur:
            cur.execute(
                'DELETE FROM pages WHERE path = %s OR path LIKE %s',
                (prefix, f"{prefix}/%"),
            )
            deleted = cur.rowcount
        conn.commit()
    return deleted


def _wiki_author_id(conn) -> int:
    with conn.cursor() as cur:
        cur.execute('SELECT id FROM users ORDER BY id LIMIT 1')
        row = cur.fetchone()
    if not row:
        raise RuntimeError("Wiki.js has no users; complete wiki setup first.")
    return int(row[0])


class WikiDbBulkWriter:
    """
    Batch-insert pages into Wiki.js Postgres (SDE content still comes from eve_sde ORM).
    One rebuildTree + flushCache via GraphQL after import.
    """

    def __init__(
        self,
        *,
        skip_existing: bool = True,
        batch_size: int = 500,
        locale: str = LOCALE,
    ):
        self.skip_existing = skip_existing
        self.batch_size = max(50, batch_size)
        self.locale = locale
        self._author_id: int | None = None
        self._existing_paths: set[str] = set()
        self._pending: list[tuple] = []
        self._lock = threading.Lock()

    def preload_paths(self, prefix: str) -> int:
        prefix = prefix.strip("/")
        with _connect() as conn:
            with conn.cursor() as cur:
                cur.execute(
                    'SELECT path FROM pages WHERE path = %s OR path LIKE %s',
                    (prefix, f"{prefix}/%"),
                )
                for (path,) in cur.fetchall():
                    self._existing_paths.add((path or "").strip("/"))
        return len(self._existing_paths)

    def upsert(
        self,
        *,
        path: str,
        title: str,
        content: str,
        description: str = "",
        dry_run: bool = False,
        force_update: bool = False,
    ) -> str:
        path = path.strip("/")
        if dry_run:
            return "dry-run"
        if path in self._existing_paths and force_update:
            return self._update_existing(path, title, content, description)
        if self.skip_existing and path in self._existing_paths:
            return "skipped"

        if self._author_id is None:
            with _connect() as conn:
                self._author_id = _wiki_author_id(conn)

        title = (title or path.split("/")[-1])[:255]
        description = (description or title)[:250]
        now = _utc_now_iso()
        page_hash = page_content_hash(path, content)
        row = (
            path,
            page_hash,
            title,
            description,
            False,
            True,
            "",
            "",
            "",
            content,
            CONTENT_TYPE,
            now,
            now,
            EDITOR,
            self.locale,
            self._author_id,
            self._author_id,
            json.dumps({"js": "", "css": ""}),
        )
        with self._lock:
            self._pending.append(row)
            if len(self._pending) >= self.batch_size:
                self._flush_locked()
            self._existing_paths.add(path)
        return "created"

    def _update_existing(
        self, path: str, title: str, content: str, description: str
    ) -> str:
        title = (title or path.split("/")[-1])[:255]
        description = (description or title)[:250]
        now = _utc_now_iso()
        page_hash = page_content_hash(path, content)
        with _connect() as conn:
            with conn.cursor() as cur:
                cur.execute(
                    """
                    UPDATE pages
                    SET hash = %s, title = %s, description = %s, content = %s,
                        "updatedAt" = %s, "isPublished" = TRUE
                    WHERE path = %s AND "localeCode" = %s
                    """,
                    (
                        page_hash,
                        title,
                        description,
                        content,
                        now,
                        path,
                        self.locale,
                    ),
                )
                if cur.rowcount == 0:
                    self._existing_paths.discard(path)
                    return self.upsert(
                        path=path,
                        title=title,
                        content=content,
                        description=description,
                        force_update=False,
                    )
            conn.commit()
        return "updated"

    def flush(self) -> int:
        with self._lock:
            return self._flush_locked()

    def _flush_locked(self) -> int:
        if not self._pending:
            return 0
        rows = self._pending
        self._pending = []

        with _connect() as conn:
            if self._author_id is None:
                self._author_id = _wiki_author_id(conn)
            author = self._author_id
            values = [
                (
                    path,
                    h,
                    title,
                    desc,
                    priv,
                    pub,
                    private_ns,
                    pub_start,
                    pub_end,
                    content,
                    ctype,
                    created,
                    updated,
                    editor,
                    locale,
                    author,
                    author,
                    extra,
                )
                for (
                    path,
                    h,
                    title,
                    desc,
                    priv,
                    pub,
                    private_ns,
                    pub_start,
                    pub_end,
                    content,
                    ctype,
                    created,
                    updated,
                    editor,
                    locale,
                    _a1,
                    _a2,
                    extra,
                ) in rows
            ]
            with conn.cursor() as cur:
                execute_values(
                    cur,
                    """
                    INSERT INTO pages (
                        path, hash, title, description,
                        "isPrivate", "isPublished",
                        "privateNS", "publishStartDate", "publishEndDate",
                        content, "contentType",
                        "createdAt", "updatedAt",
                        "editorKey", "localeCode",
                        "authorId", "creatorId", extra
                    ) VALUES %s
                    """,
                    values,
                    page_size=len(values),
                )
            conn.commit()
        return len(rows)
