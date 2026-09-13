"""Coalition calendar — character events, moon windows, structure fuel."""

from __future__ import annotations

from datetime import UTC, date, datetime, timedelta
from typing import Any

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.tools import AuditProfile, AuthedStructure
from app.services.audit_snapshot import load_snapshot
from app.services.moon_timing import moon_mining_timing


async def calendar_events(
    session: AsyncSession,
    *,
    character_id: int | None = None,
    month: str | None = None,
) -> dict[str, Any]:
    """Build a month of events from ESI calendar, moon timing, and fuel timers."""
    today = date.today()
    if month:
        try:
            y, m = month.split("-")
            month_start = date(int(y), int(m), 1)
        except ValueError:
            month_start = today.replace(day=1)
    else:
        month_start = today.replace(day=1)
    if month_start.month == 12:
        month_end = date(month_start.year + 1, 1, 1) - timedelta(days=1)
    else:
        month_end = date(month_start.year, month_start.month + 1, 1) - timedelta(days=1)

    events: list[dict[str, Any]] = []

    # Character ESI calendar (from audit snapshot)
    if character_id:
        profile = await session.scalar(
            select(AuditProfile).where(AuditProfile.character_id == character_id)
        )
        if profile:
            snap = load_snapshot(profile)
            for ev in snap.get("calendar_events") or []:
                if not isinstance(ev, dict):
                    continue
                raw = ev.get("event_date") or ev.get("date") or ""
                try:
                    ev_dt = datetime.fromisoformat(str(raw).replace("Z", "+00:00"))
                    ev_day = ev_dt.date()
                except ValueError:
                    continue
                if month_start <= ev_day <= month_end:
                    events.append(
                        {
                            "id": f"cal-{ev.get('event_id') or ev.get('title')}-{ev_day}",
                            "date": ev_day.isoformat(),
                            "time": ev_dt.strftime("%H:%M") if ev_dt.tzinfo else "",
                            "title": str(ev.get("title") or "Calendar event"),
                            "kind": "calendar",
                            "importance": int(ev.get("importance") or 0),
                            "source": "esi_calendar",
                        }
                    )

    # Moon mining timing markers
    timing = await moon_mining_timing(session, days=60)
    for row in timing.get("structures") or []:
        for key, kind, title_prefix in (
            ("last_mined_date", "moon_activity", "Mined"),
            ("estimated_window_end", "moon_window", "Window ends"),
            ("next_pop_estimate", "moon_pop", "Est. next pop"),
        ):
            d = row.get(key)
            if not d:
                continue
            try:
                day = date.fromisoformat(str(d)[:10])
            except ValueError:
                continue
            if month_start <= day <= month_end:
                events.append(
                    {
                        "id": f"moon-{row['structure_name']}-{key}-{day}",
                        "date": day.isoformat(),
                        "time": "",
                        "title": f"{title_prefix}: {row['structure_name']}",
                        "kind": kind,
                        "importance": 1 if kind == "moon_pop" else 0,
                        "source": "moon_timing",
                        "meta": {"phase": row.get("phase"), "structure": row["structure_name"]},
                    }
                )

    # Structure fuel expiry
    now = datetime.now(UTC)
    structures = (await session.scalars(select(AuthedStructure))).all()
    for s in structures:
        if not s.fuel_expires_at:
            continue
        day = s.fuel_expires_at.date()
        if month_start <= day <= month_end:
            hours = (s.fuel_expires_at - now).total_seconds() / 3600.0
            events.append(
                {
                    "id": f"fuel-{s.structure_id}-{day}",
                    "date": day.isoformat(),
                    "time": s.fuel_expires_at.strftime("%H:%M"),
                    "title": f"Fuel expires: {s.structure_name}",
                    "kind": "fuel",
                    "importance": 2 if hours < 72 else 1,
                    "source": "structure_fuel",
                    "meta": {"hours_remaining": round(hours, 1), "structure_id": s.structure_id},
                }
            )

    events.sort(key=lambda e: (e["date"], e.get("time") or "99:99", e["title"]))

    # Month grid skeleton
    weeks: list[list[dict[str, Any]]] = []
    # Monday-start week
    cursor = month_start - timedelta(days=month_start.weekday())
    end_pad = month_end + timedelta(days=(6 - month_end.weekday()))
    while cursor <= end_pad:
        week: list[dict[str, Any]] = []
        for _ in range(7):
            day_events = [e for e in events if e["date"] == cursor.isoformat()]
            week.append(
                {
                    "date": cursor.isoformat(),
                    "in_month": month_start <= cursor <= month_end,
                    "is_today": cursor == date.today(),
                    "events": day_events,
                    "event_count": len(day_events),
                }
            )
            cursor += timedelta(days=1)
        weeks.append(week)

    return {
        "month": month_start.strftime("%Y-%m"),
        "month_label": month_start.strftime("%B %Y"),
        "events": events,
        "weeks": weeks,
        "summary": {
            "total_events": len(events),
            "calendar": sum(1 for e in events if e["kind"] == "calendar"),
            "moon": sum(1 for e in events if e["kind"].startswith("moon")),
            "fuel": sum(1 for e in events if e["kind"] == "fuel"),
        },
    }
