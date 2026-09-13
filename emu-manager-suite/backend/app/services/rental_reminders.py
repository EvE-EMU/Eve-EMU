"""EVE mail + Discord reminders for rental bills."""

from __future__ import annotations

import json
import logging
from datetime import UTC, datetime

import httpx
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import MessageTemplate, OrgSettings
from app.models.rentals import MoonLease, RentalBill, RentableMoon
from app.services.eve_mail import send_character_mail
from app.services.rental_program import load_rental_settings, parse_reminder_days
from app.services.template_engine import render_template

logger = logging.getLogger(__name__)


async def send_rental_reminders(session: AsyncSession) -> int:
    cfg = await load_rental_settings(session)
    if not cfg.enabled:
        return 0

    org = await session.scalar(select(OrgSettings).limit(1))
    days = parse_reminder_days(cfg.reminder_days_json)
    today = datetime.now(UTC).date()
    sent = 0

    bills = await session.scalars(
        select(RentalBill).where(
            RentalBill.status.in_(
                (RentalBill.STATUS_OPEN, RentalBill.STATUS_PARTIAL, RentalBill.STATUS_OVERDUE)
            )
        )
    )
    for bill in bills.all():
        overdue_days = (today - bill.due_at).days
        if overdue_days not in days:
            continue
        try:
            reminders = json.loads(bill.reminders_sent_json or "{}")
        except json.JSONDecodeError:
            reminders = {}
        key = str(overdue_days)
        if reminders.get(key):
            continue

        lease = await session.get(MoonLease, bill.lease_id)
        if not lease or not lease.contact_character_id:
            continue
        moon = await session.get(RentableMoon, lease.moon_id)
        structure_name = moon.structure_name if moon else "moon structure"
        balance = bill.amount_due_isk - bill.amount_paid_isk

        variables = {
            "bill_number": bill.bill_number,
            "structure_name": structure_name,
            "amount_due": str(balance),
            "due_at": bill.due_at.isoformat(),
            "payment_reference": bill.bill_number,
            "renter_corp": lease.renter_corporation_name,
        }

        tpl = await session.scalar(
            select(MessageTemplate).where(
                MessageTemplate.slug == "rental_bill_reminder",
                MessageTemplate.active.is_(True),
            )
        )
        if tpl:
            subject, body = render_template(tpl, variables)
        else:
            subject = f"Moon rent due — {bill.bill_number}"
            body = (
                f"Rent for {structure_name} is due.\n\n"
                f"Amount: {balance:,.0f} ISK\n"
                f"Due: {bill.due_at}\n"
                f"Reference: {bill.bill_number}\n"
            )

        ok = False
        if org and org.mail_enabled:
            ok, err = await send_character_mail(
                session,
                recipient_character_id=lease.contact_character_id,
                subject=subject,
                body=body,
            )
            if not ok:
                logger.warning("rental reminder mail failed: %s", err)

        if org and org.discord_webhook_url:
            try:
                async with httpx.AsyncClient(timeout=15.0) as client:
                    await client.post(
                        org.discord_webhook_url,
                        json={
                            "content": f"**Moon rent reminder** — {lease.renter_corporation_name}\n{body[:1800]}",
                        },
                    )
                ok = True
            except Exception as exc:
                logger.warning("rental discord reminder failed: %s", exc)

        if ok:
            reminders[key] = datetime.now(UTC).isoformat()
            bill.reminders_sent_json = json.dumps(reminders)
            sent += 1

    return sent
