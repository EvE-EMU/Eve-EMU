"""SQLite event store for webhooks + export snapshots."""

from __future__ import annotations

import json
import sqlite3
from pathlib import Path
from typing import Any

from report_app.config import settings


def _db_path() -> Path:
    return Path(settings.history_db)


def _connect() -> sqlite3.Connection:
    path = _db_path()
    path.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(str(path))
    conn.row_factory = sqlite3.Row
    return conn


def init_db() -> None:
    with _connect() as conn:
        conn.executescript(
            """
            CREATE TABLE IF NOT EXISTS events (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                link_id TEXT NOT NULL,
                event_id TEXT,
                site_id TEXT,
                event_type TEXT,
                action TEXT,
                model TEXT,
                occurred_at TEXT,
                payload_json TEXT NOT NULL,
                source TEXT NOT NULL DEFAULT 'webhook',
                ingested_at TEXT NOT NULL DEFAULT (datetime('now'))
            );
            CREATE INDEX IF NOT EXISTS idx_events_link ON events(link_id);
            CREATE INDEX IF NOT EXISTS idx_events_model ON events(model);
            CREATE INDEX IF NOT EXISTS idx_events_occurred ON events(occurred_at);
            """
        )


def insert_event(
    link_id: str,
    *,
    event_id: str | None,
    site_id: str | None,
    event_type: str,
    action: str | None,
    model: str | None,
    occurred_at: str | None,
    payload: dict[str, Any],
    source: str = "webhook",
) -> int:
    init_db()
    with _connect() as conn:
        cur = conn.execute(
            """
            INSERT INTO events (
                link_id, event_id, site_id, event_type, action, model,
                occurred_at, payload_json, source
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                link_id,
                event_id,
                site_id,
                event_type,
                action,
                model,
                occurred_at,
                json.dumps(payload, default=str),
                source,
            ),
        )
        return int(cur.lastrowid)


def query_events(
    link_id: str,
    *,
    model: str | None = None,
    since: str | None = None,
    limit: int = 100,
    offset: int = 0,
) -> dict[str, Any]:
    init_db()
    clauses = ["link_id = ?"]
    params: list[Any] = [link_id]
    if model:
        clauses.append("model = ?")
        params.append(model)
    if since:
        clauses.append("occurred_at >= ?")
        params.append(since)
    where = " AND ".join(clauses)
    params.extend([limit, offset])

    with _connect() as conn:
        total = conn.execute(
            f"SELECT COUNT(*) FROM events WHERE {where}", params[:-2]
        ).fetchone()[0]
        rows = conn.execute(
            f"""
            SELECT * FROM events WHERE {where}
            ORDER BY occurred_at DESC, id DESC
            LIMIT ? OFFSET ?
            """,
            params,
        ).fetchall()

    items = []
    for row in rows:
        items.append(
            {
                "id": row["id"],
                "event_id": row["event_id"],
                "site_id": row["site_id"],
                "event_type": row["event_type"],
                "action": row["action"],
                "model": row["model"],
                "occurred_at": row["occurred_at"],
                "source": row["source"],
                "ingested_at": row["ingested_at"],
                "payload": json.loads(row["payload_json"]),
            }
        )
    return {"link_id": link_id, "total": total, "limit": limit, "offset": offset, "items": items}
