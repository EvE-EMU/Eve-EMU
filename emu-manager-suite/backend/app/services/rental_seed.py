"""Default rental templates and settings on startup."""

from __future__ import annotations

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import MessageTemplate
from app.services.rental_program import load_rental_settings


async def ensure_rental_defaults(session: AsyncSession) -> None:
    await load_rental_settings(session)

    tpl = await session.scalar(
        select(MessageTemplate).where(MessageTemplate.slug == "rental_bill_reminder")
    )
    if not tpl:
        session.add(
            MessageTemplate(
                slug="rental_bill_reminder",
                name="Moon rent reminder",
                channel="mail",
                subject="Moon rent due — {{ bill_number }}",
                body=(
                    "Greetings,\n\n"
                    "Rent for {{ structure_name }} ({{ renter_corp }}) is due.\n\n"
                    "Amount: {{ amount_due }} ISK\n"
                    "Due date: {{ due_at }}\n"
                    "Payment reference: {{ payment_reference }}\n\n"
                    "Pay into the landlord corp wallet with the reference above.\n"
                ),
                variables_json='["bill_number","structure_name","amount_due","due_at","payment_reference","renter_corp"]',
            )
        )
