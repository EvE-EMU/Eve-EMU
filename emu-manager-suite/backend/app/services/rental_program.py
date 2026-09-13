"""Bill generation, payment matching, application approval."""

from __future__ import annotations

import calendar
import json
import logging
import re
from datetime import UTC, date, datetime, timedelta
from decimal import Decimal

import httpx
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import settings
from app.models.rentals import (
    MoonLease,
    RentalApplication,
    RentalBill,
    RentalProgramSettings,
    RentableMoon,
)
from app.services.esi import bearer_token

logger = logging.getLogger(__name__)

_ESI = "https://esi.evetech.net/latest"
_UA = "EVE-EMU-EMUMS/1.0 (+https://emums.eve-emu.com; rentals)"


async def load_rental_settings(session: AsyncSession) -> RentalProgramSettings:
    row = await session.scalar(select(RentalProgramSettings).limit(1))
    if row:
        return row
    row = RentalProgramSettings(
        landlord_corporation_id=settings.killboard_corporation_id or 0,
        landlord_corporation_name="",
    )
    session.add(row)
    await session.flush()
    return row


def _month_end(d: date) -> date:
    last = calendar.monthrange(d.year, d.month)[1]
    return d.replace(day=last)


def _bill_ref_pattern(prefix: str) -> re.Pattern[str]:
    safe = re.escape(prefix.strip() or "RENT")
    return re.compile(rf"{safe}-(\d{{4}}-\d{{2}}-\d{{3,}})", re.I)


async def _next_bill_number(session: AsyncSession, prefix: str, period: date) -> str:
    stem = f"{prefix}-{period.strftime('%Y-%m')}"
    existing = await session.scalars(
        select(RentalBill.bill_number).where(RentalBill.bill_number.like(f"{stem}-%"))
    )
    seq = max((int(n.rsplit("-", 1)[-1]) for n in existing.all() if n.rsplit("-", 1)[-1].isdigit()), default=0) + 1
    return f"{stem}-{seq:03d}"


async def generate_monthly_bills(session: AsyncSession, *, period_month: date | None = None) -> int:
    cfg = await load_rental_settings(session)
    if not cfg.enabled:
        return 0
    today = datetime.now(UTC).date()
    if period_month is None:
        period_month = today.replace(day=1)
    period_end = _month_end(period_month)
    created = 0
    leases = await session.scalars(
        select(MoonLease).where(MoonLease.status == MoonLease.STATUS_ACTIVE)
    )
    for lease in leases.all():
        if lease.started_at > period_end or lease.monthly_rent_isk <= 0:
            continue
        existing = await session.scalar(
            select(RentalBill).where(
                RentalBill.lease_id == lease.id,
                RentalBill.period_start == period_month,
            )
        )
        if existing:
            continue
        bill_number = await _next_bill_number(session, cfg.payment_reference_prefix, period_month)
        session.add(
            RentalBill(
                lease_id=lease.id,
                bill_number=bill_number,
                period_start=period_month,
                period_end=period_end,
                amount_due_isk=lease.monthly_rent_isk,
                due_at=period_end + timedelta(days=cfg.due_grace_days),
                status=RentalBill.STATUS_OPEN,
            )
        )
        created += 1
    return created


async def mark_overdue_bills(session: AsyncSession) -> int:
    today = datetime.now(UTC).date()
    count = 0
    rows = await session.scalars(
        select(RentalBill).where(
            RentalBill.status.in_(
                (RentalBill.STATUS_OPEN, RentalBill.STATUS_PARTIAL)
            ),
            RentalBill.due_at < today,
        )
    )
    for bill in rows.all():
        if bill.status != RentalBill.STATUS_OVERDUE:
            bill.status = RentalBill.STATUS_OVERDUE
            count += 1
    return count


async def apply_bill_payment(
    bill: RentalBill,
    amount: Decimal,
    *,
    wallet_tx_id: int | None = None,
) -> None:
    bill.amount_paid_isk += amount
    if wallet_tx_id:
        bill.wallet_transaction_id = wallet_tx_id
    if bill.amount_paid_isk >= bill.amount_due_isk:
        bill.status = RentalBill.STATUS_PAID
        bill.paid_at = datetime.now(UTC)
    elif bill.amount_paid_isk > 0:
        bill.status = RentalBill.STATUS_PARTIAL


async def poll_wallet_payments(session: AsyncSession) -> int:
    cfg = await load_rental_settings(session)
    if not cfg.enabled or not cfg.landlord_corporation_id:
        return 0
    char_id = cfg.wallet_poll_character_id
    token = await bearer_token(session, character_id=char_id) if char_id else await bearer_token(session)
    if not token:
        logger.warning("rentals: no ESI token for wallet poll")
        return 0

    division = cfg.wallet_division
    corp_id = cfg.landlord_corporation_id
    url = f"{_ESI}/corporations/{corp_id}/wallets/{division}/journal/"
    matched = 0
    ref_re = _bill_ref_pattern(cfg.payment_reference_prefix)

    async with httpx.AsyncClient(timeout=30.0) as client:
        page = 1
        while page <= 5:
            resp = await client.get(
                url,
                params={"page": page},
                headers={"Authorization": f"Bearer {token}", "User-Agent": _UA},
            )
            if resp.status_code != 200:
                logger.warning("rentals wallet journal: %s", resp.status_code)
                break
            entries = resp.json()
            if not entries:
                break
            for entry in entries:
                if float(entry.get("amount") or 0) <= 0:
                    continue
                tx_id = int(entry.get("id") or 0)
                if not tx_id:
                    continue
                desc = str(entry.get("description") or "")
                m = ref_re.search(desc)
                if not m:
                    continue
                bill_number = m.group(0).upper()
                bill = await session.scalar(
                    select(RentalBill).where(RentalBill.bill_number == bill_number)
                )
                if not bill or bill.status == RentalBill.STATUS_PAID:
                    continue
                if bill.wallet_transaction_id == tx_id:
                    continue
                await apply_bill_payment(
                    bill, Decimal(str(entry.get("amount"))), wallet_tx_id=tx_id
                )
                matched += 1
            if len(entries) < 1000:
                break
            page += 1
    return matched


async def approve_application(
    session: AsyncSession,
    application: RentalApplication,
    *,
    reviewer_character_id: int,
    reviewer_character_name: str,
    notes: str = "",
) -> MoonLease:
    if application.status != RentalApplication.STATUS_PENDING:
        raise ValueError("Application is not pending")

    moon = await session.get(RentableMoon, application.moon_id)
    if not moon:
        raise ValueError("Moon not found")

    today = datetime.now(UTC).date()
    ends = today + timedelta(days=application.duration_days)

    application.status = RentalApplication.STATUS_APPROVED
    application.reviewed_by_character_id = reviewer_character_id
    application.reviewed_by_character_name = reviewer_character_name
    application.reviewed_at = datetime.now(UTC)
    if notes:
        application.notes = notes

    lease = MoonLease(
        moon_id=moon.id,
        application_id=application.id,
        renter_corporation_id=application.renter_corporation_id,
        renter_corporation_name=application.renter_corporation_name,
        contact_character_id=application.applicant_character_id,
        contact_character_name=application.applicant_character_name,
        started_at=today,
        ends_at=ends,
        monthly_rent_isk=application.monthly_rent_offered_isk or moon.monthly_rent_isk,
        status=MoonLease.STATUS_ACTIVE,
    )
    session.add(lease)
    moon.status = "leased"
    return lease


async def reject_application(
    application: RentalApplication,
    *,
    reviewer_character_id: int,
    reviewer_character_name: str,
    notes: str = "",
) -> None:
    if application.status != RentalApplication.STATUS_PENDING:
        raise ValueError("Application is not pending")
    application.status = RentalApplication.STATUS_REJECTED
    application.reviewed_by_character_id = reviewer_character_id
    application.reviewed_by_character_name = reviewer_character_name
    application.reviewed_at = datetime.now(UTC)
    if notes:
        application.notes = notes


async def auto_approve_pending(session: AsyncSession) -> int:
    cfg = await load_rental_settings(session)
    if not cfg.auto_approve_applications:
        return 0
    count = 0
    rows = await session.scalars(
        select(RentalApplication).where(
            RentalApplication.status == RentalApplication.STATUS_PENDING
        )
    )
    for app in rows.all():
        await approve_application(
            session,
            app,
            reviewer_character_id=0,
            reviewer_character_name="system",
            notes="Auto-approved",
        )
        count += 1
    return count


async def expire_due_leases(session: AsyncSession) -> int:
    """Mark active leases past ``ends_at`` as expired and free the moon."""
    today = datetime.now(UTC).date()
    count = 0
    rows = await session.scalars(
        select(MoonLease).where(
            MoonLease.status == MoonLease.STATUS_ACTIVE,
            MoonLease.ends_at.isnot(None),
            MoonLease.ends_at < today,
        )
    )
    for lease in rows.all():
        lease.status = MoonLease.STATUS_EXPIRED
        moon = await session.get(RentableMoon, lease.moon_id)
        if moon:
            moon.status = "available"
        count += 1
    return count


async def run_rental_jobs(session: AsyncSession) -> dict[str, int]:
    from app.services.rental_reminders import send_rental_reminders

    auto = await auto_approve_pending(session)
    bills = await generate_monthly_bills(session)
    overdue = await mark_overdue_bills(session)
    payments = await poll_wallet_payments(session)
    reminders = await send_rental_reminders(session)
    return {
        "bills_created": bills,
        "bills_marked_overdue": overdue,
        "payments_matched": payments,
        "reminders_sent": reminders,
        "applications_auto_approved": auto,
    }


def parse_reminder_days(raw: str) -> list[int]:
    try:
        data = json.loads(raw or "[]")
        return sorted({int(x) for x in data if int(x) >= 0})
    except (TypeError, ValueError, json.JSONDecodeError):
        return [3, 7, 14, 21]
