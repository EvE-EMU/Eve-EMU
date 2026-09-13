"""Moon tax billing — aggregate mining logs into invoices."""

from __future__ import annotations

import fnmatch
import logging
from collections import defaultdict
from datetime import UTC, date, datetime, timedelta
from decimal import Decimal

from sqlalchemy import and_, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import Invoice, MiningLog, StructureTaxRule

logger = logging.getLogger(__name__)


def _tax_rate_for_log(rule: StructureTaxRule, moon_rarity: str) -> Decimal:
    rarity = (moon_rarity or "r16").lower()
    if rarity == "r64":
        return Decimal(rule.r64_pct)
    if rarity == "r32":
        return Decimal(rule.r32_pct)
    return Decimal(rule.r16_pct)


def _match_tax_rule(rules: list[StructureTaxRule], structure_name: str) -> StructureTaxRule | None:
    for rule in sorted(rules, key=lambda r: r.priority):
        pattern = (rule.pattern or "*").strip()
        if fnmatch.fnmatch(structure_name.lower(), pattern.lower()):
            return rule
    return None


def _iso_week_bounds(d: date) -> tuple[date, date]:
    """Monday–Sunday bounds for the ISO week containing ``d``."""
    start = d - timedelta(days=d.weekday())
    return start, start + timedelta(days=6)


async def _next_invoice_number(session: AsyncSession, period_end: date) -> str:
    stem = f"MT-{period_end.strftime('%y')}{period_end.isocalendar().week:02d}"
    existing = await session.scalars(
        select(Invoice.invoice_number).where(Invoice.invoice_number.like(f"{stem}-%"))
    )
    seq = max(
        (int(n.rsplit("-", 1)[-1]) for n in existing.all() if n.rsplit("-", 1)[-1].isdigit()),
        default=0,
    ) + 1
    return f"{stem}-{seq:04d}"


async def generate_invoices_for_period(
    session: AsyncSession,
    *,
    period_start: date | None = None,
    period_end: date | None = None,
) -> int:
    """Create moon tax invoices from mining logs for a tracking period."""
    today = datetime.now(UTC).date()
    if period_end is None:
        period_end = today - timedelta(days=today.weekday() + 1)  # prior Sunday
    if period_start is None:
        period_start, _ = _iso_week_bounds(period_end)

    rules = list(
        (
            await session.scalars(
                select(StructureTaxRule)
                .where(StructureTaxRule.active.is_(True))
                .order_by(StructureTaxRule.priority)
            )
        ).all()
    )
    if not rules:
        logger.warning("EMUMS billing: no active structure tax rules")
        return 0

    logs = await session.scalars(
        select(MiningLog).where(
            and_(MiningLog.mined_date >= period_start, MiningLog.mined_date <= period_end)
        )
    )

    by_character: dict[int, dict] = defaultdict(
        lambda: {
            "character_name": "",
            "structures": set(),
            "tax_due": Decimal("0"),
        }
    )

    for log in logs.all():
        rule = _match_tax_rule(rules, log.structure_name)
        if not rule:
            continue
        rate = _tax_rate_for_log(rule, log.moon_rarity)
        if rate <= 0:
            continue
        tax = (Decimal(log.isk_value) * rate / Decimal("100")).quantize(Decimal("0.01"))
        if tax <= 0:
            continue
        bucket = by_character[int(log.character_id)]
        bucket["character_name"] = log.character_name
        bucket["structures"].add(log.structure_name)
        bucket["tax_due"] += tax

    created = 0
    due_at = period_end + timedelta(days=14)

    for character_id, data in by_character.items():
        if data["tax_due"] <= 0:
            continue

        structure_label = ", ".join(sorted(data["structures"])[:3])
        if len(data["structures"]) > 3:
            structure_label += f" (+{len(data['structures']) - 3} more)"

        existing = await session.scalar(
            select(Invoice).where(
                Invoice.character_name == data["character_name"],
                Invoice.structure_name == structure_label,
                Invoice.due_at == due_at,
                Invoice.status.in_(("open", "overdue", "partial")),
            )
        )
        if existing:
            continue

        invoice_number = await _next_invoice_number(session, period_end)
        session.add(
            Invoice(
                invoice_number=invoice_number,
                character_name=data["character_name"],
                corporation_name="",
                structure_name=structure_label,
                total_due_isk=data["tax_due"],
                amount_paid_isk=Decimal("0"),
                status="open",
                due_at=due_at,
                on_naughty_list=False,
            )
        )
        created += 1
        logger.info(
            "EMUMS billing: invoice %s for %s (%s ISK)",
            invoice_number,
            data["character_name"],
            data["tax_due"],
        )

    return created
