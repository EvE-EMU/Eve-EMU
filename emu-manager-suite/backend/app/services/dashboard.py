"""Dashboard aggregation service."""

from __future__ import annotations

import json

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import DashboardSnapshot, Invoice, OrgSettings
from app.schemas import DashboardOut, InvoiceOut


async def build_dashboard(session: AsyncSession) -> DashboardOut:
    settings = await session.scalar(select(OrgSettings).limit(1))
    tagline = settings.propaganda_tagline if settings else "MOON OUTPUT FOR THE WAR EFFORT"

    snapshots = {
        row.metric_key: json.loads(row.payload_json)
        for row in (await session.scalars(select(DashboardSnapshot))).all()
    }

    open_count = await session.scalar(
        select(func.count()).select_from(Invoice).where(Invoice.status == "open")
    )
    overdue = await session.scalar(
        select(func.count()).select_from(Invoice).where(Invoice.on_naughty_list.is_(True))
    )
    total_due = await session.scalar(
        select(func.sum(Invoice.total_due_isk - Invoice.amount_paid_isk)).where(
            Invoice.status.in_(("open", "partial"))
        )
    )
    mining_vol = sum(p.get("volume", 0) for p in snapshots.get("mining_by_day", [])[-7:])

    outstanding_isk = await session.scalar(
        select(func.sum(Invoice.total_due_isk - Invoice.amount_paid_isk)).where(
            Invoice.status.in_(("open", "partial"))
        )
    )
    paid_isk = await session.scalar(select(func.sum(Invoice.amount_paid_isk)))

    kpis = [
        {"label": "Open invoices", "value": str(open_count or 0), "tone": "warn"},
        {"label": "Overdue miners", "value": str(overdue or 0), "tone": "danger"},
        {"label": "ISK outstanding", "value": f"{float(total_due or 0):,.0f}", "tone": "accent"},
        {"label": "7d volume (u³)", "value": f"{mining_vol:,}", "tone": "ok"},
    ]

    recent = await session.scalars(
        select(Invoice).order_by(Invoice.due_at.desc()).limit(8)
    )

    return DashboardOut(
        tagline=tagline,
        kpis=kpis,
        mining_by_day=snapshots.get("mining_by_day", []),
        rarity_mix=snapshots.get("rarity_mix", []),
        top_structures=snapshots.get("top_structures", []),
        invoice_status=[
            {"status": "Outstanding", "isk": float(outstanding_isk or 0)},
            {"status": "Paid", "isk": float(paid_isk or 0)},
        ],
        recent_invoices=[InvoiceOut.model_validate(i) for i in recent.all()],
    )
