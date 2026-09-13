"""Demo data for visual-first dashboards (no ESI required)."""

from __future__ import annotations

import json
import random
from datetime import date, timedelta
from decimal import Decimal

from sqlalchemy.ext.asyncio import AsyncSession

from app.models import (
    DashboardSnapshot,
    Invoice,
    MessageTemplate,
    MiningLog,
    OrgSettings,
    StructureTaxRule,
)

DEFAULT_TEMPLATES = [
    {
        "slug": "invoice-mail",
        "name": "Moon tax invoice (EVE mail)",
        "channel": "mail",
        "subject": "MOON TAX — {{ invoice_number }}",
        "body": (
            "Citizen {{ character_name }},\n\n"
            "Your contribution to the industrial war effort is due.\n"
            "Structure: {{ structure_name }}\n"
            "Amount: {{ total_due_isk }} ISK\n"
            "Reference: {{ invoice_number }}\n\n"
            "— Office of Lunar Extraction\n"
        ),
        "variables_json": json.dumps(
            ["character_name", "structure_name", "total_due_isk", "invoice_number"]
        ),
    },
    {
        "slug": "discord-new-bills",
        "name": "Discord — new tax bills",
        "channel": "discord",
        "subject": "",
        "body": (
            "**MOON TAX BATCH ISSUED**\n"
            "New bills: {{ bill_count }} · Total due: {{ total_isk }} ISK\n"
            "{{ tagline }}"
        ),
        "variables_json": json.dumps(["bill_count", "total_isk", "tagline"]),
    },
    {
        "slug": "report-weekly",
        "name": "Weekly extraction report",
        "channel": "report",
        "subject": "Weekly moon output — {{ week_label }}",
        "body": (
            "# Industrial Directorate Weekly Report\n\n"
            "Period: {{ week_label }}\n"
            "Structures active: {{ structure_count }}\n"
            "Volume (M³): {{ total_volume }}\n"
        ),
        "variables_json": json.dumps(["week_label", "structure_count", "total_volume"]),
    },
]


async def seed_demo(session: AsyncSession) -> None:
    settings = OrgSettings(
        org_name="EvE EMU | Edging Gone Wild",
        corporation_id=98835239,
        observer_corporation_id=98633922,
        tax_corp_name="",
        propaganda_tagline="MOON OUTPUT FOR THE WAR EFFORT — EVERY BAR REFINED COUNTS",
    )
    session.add(settings)

    for rule in (
        ("*PRIVATE*", 10, 0, 0, 0),
        ("*NATIONALISED*", 20, 100, 100, 100),
        ("*PUBLIC*", 50, 20, 30, 40),
        ("*", 100, 20, 30, 40),
    ):
        session.add(
            StructureTaxRule(
                pattern=rule[0],
                priority=rule[1],
                r16_pct=Decimal(rule[2]),
                r32_pct=Decimal(rule[3]),
                r64_pct=Decimal(rule[4]),
            )
        )

    structures = [
        "DS-LO3 - PUBLIC P9M1",
        "0TKF-6 - NATIONALISED R64",
        "J115404 - PRIVATE STRIP",
        "B-DBYQ - PUBLIC R16",
        "C-J6MT - PUBLIC MIX",
    ]
    rarities = ["r4", "r8", "r16", "r32", "r64"]
    ores = ["Bitumens", "Coesite", "Sylvite", "Chromite", "Loparite"]
    chars = ["Rexan Darkstar", "Zuene Ocard", "Pilot Alpha", "Miner Beta", "Corp Alt 7"]
    today = date.today()
    for day_offset in range(28):
        d = today - timedelta(days=day_offset)
        for _ in range(random.randint(3, 9)):
            qty = random.randint(500, 12000)
            rarity = random.choice(rarities)
            unit = Decimal(random.randint(800, 45000))
            session.add(
                MiningLog(
                    mined_date=d,
                    structure_name=random.choice(structures),
                    character_id=random.randint(90000000, 99999999),
                    character_name=random.choice(chars),
                    type_name=random.choice(ores),
                    type_id=random.randint(45000, 46000),
                    moon_rarity=rarity,
                    quantity=qty,
                    isk_value=unit * qty,
                )
            )

    statuses = ["open", "partial", "paid", "open", "open"]
    for i in range(24):
        due = today + timedelta(days=random.randint(-14, 21))
        total = Decimal(random.randint(5_000_000, 850_000_000))
        paid = Decimal(0) if statuses[i % len(statuses)] == "open" else total
        session.add(
            Invoice(
                invoice_number=f"MT-{today.strftime('%y')}{today.isocalendar().week:02d}-{1000+i:04d}",
                character_name=random.choice(chars),
                corporation_name="Guns-R-Us Toy Company",
                structure_name=random.choice(structures),
                total_due_isk=total,
                amount_paid_isk=paid,
                status=statuses[i % len(statuses)] if paid == 0 else "paid",
                due_at=due,
                on_naughty_list=due < today and paid == 0,
            )
        )

    for t in DEFAULT_TEMPLATES:
        session.add(MessageTemplate(**t))

    await session.flush()
    await _refresh_snapshots(session)


async def _refresh_snapshots(session: AsyncSession) -> None:
    """Build chart JSON blobs — called after seed and by dashboard service."""
    from sqlalchemy import func, select

    from app.models import MiningLog, Invoice

    by_day = await session.execute(
        select(MiningLog.mined_date, func.sum(MiningLog.quantity), func.sum(MiningLog.isk_value))
        .group_by(MiningLog.mined_date)
        .order_by(MiningLog.mined_date)
    )
    mining_series = [
        {"date": str(row[0]), "volume": int(row[1] or 0), "isk": float(row[2] or 0)}
        for row in by_day.all()
    ]

    rarity_rows = await session.execute(
        select(MiningLog.moon_rarity, func.sum(MiningLog.quantity)).group_by(MiningLog.moon_rarity)
    )
    rarity_mix = [{"rarity": r[0], "volume": int(r[1] or 0)} for r in rarity_rows.all()]

    struct_rows = await session.execute(
        select(MiningLog.structure_name, func.sum(MiningLog.isk_value))
        .group_by(MiningLog.structure_name)
        .order_by(func.sum(MiningLog.isk_value).desc())
        .limit(8)
    )
    top_structures = [{"name": s[0], "isk": float(s[1] or 0)} for s in struct_rows.all()]

    outstanding_isk = await session.scalar(
        select(func.sum(Invoice.total_due_isk - Invoice.amount_paid_isk)).where(
            Invoice.status.in_(("open", "partial"))
        )
    )
    paid_isk = await session.scalar(select(func.sum(Invoice.amount_paid_isk)))
    invoice_status = [
        {"status": "Outstanding", "isk": float(outstanding_isk or 0)},
        {"status": "Paid", "isk": float(paid_isk or 0)},
    ]

    payloads = {
        "mining_by_day": mining_series,
        "rarity_mix": rarity_mix,
        "top_structures": top_structures,
        "invoice_status": invoice_status,
    }
    for key, data in payloads.items():
        existing = await session.scalar(
            select(DashboardSnapshot).where(DashboardSnapshot.metric_key == key)
        )
        payload_str = json.dumps(data)
        if existing:
            existing.payload_json = payload_str
        else:
            session.add(DashboardSnapshot(metric_key=key, payload_json=payload_str))
