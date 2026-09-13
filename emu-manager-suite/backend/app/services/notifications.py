"""Default in-app notifications for new deployments."""

from __future__ import annotations

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import SystemNotification

DEFAULT_NOTIFICATIONS = [
    {
        "plugin": "moons",
        "type": "moon_rental_available",
        "title": "Moon available for rent",
        "body": "DS-LO3 - PUBLIC P9M1 is open for rental — 850M ISK/mo base rate.",
        "payload_json": '{"structure":"DS-LO3 - PUBLIC P9M1","rent_isk":850000000}',
    },
    {
        "plugin": "moons",
        "type": "tax_bill",
        "title": "New tax bill issued",
        "body": "Moon tax invoice MT-2612-1003 assigned to Rexan Darkstar — 412M ISK due.",
        "payload_json": '{"invoice_number":"MT-2612-1003","character":"Rexan Darkstar"}',
    },
    {
        "plugin": "moons",
        "type": "rental_bill",
        "title": "New rental bill",
        "body": "Rental invoice for 0TKF-6 - NATIONALISED R64 — 1.2B ISK due in 7 days.",
        "payload_json": '{"structure":"0TKF-6 - NATIONALISED R64","due_isk":1200000000}',
    },
    {
        "plugin": "moons",
        "type": "extraction_ready",
        "title": "Extraction cycle complete",
        "body": "B-DBYQ - PUBLIC R16 jackpot ready — 2.4B ISK estimated pull.",
        "payload_json": '{"structure":"B-DBYQ - PUBLIC R16","jackpot_isk":2400000000}',
    },
    {
        "plugin": "system",
        "type": "info",
        "title": "EMU Manager Suite online",
        "body": "Tranquility-style command interface ready. Notifications from addons will appear here.",
        "payload_json": "{}",
    },
]


async def ensure_default_notifications(session: AsyncSession) -> None:
    count = await session.scalar(select(func.count()).select_from(SystemNotification))
    if count and count > 0:
        return
    for item in DEFAULT_NOTIFICATIONS:
        session.add(SystemNotification(**item, read=False))
    await session.flush()
