"""Corp market — stock order intake and EVE mail notifications."""

from __future__ import annotations

import logging
from decimal import Decimal

from sqlalchemy.ext.asyncio import AsyncSession

from app.config import settings
from app.models import CorpMarketOrder
from app.services.eve_mail import send_character_mail
from app.services.sde_search import get_type, lookup_type_by_name

logger = logging.getLogger(__name__)


async def submit_corp_market_order(
    session: AsyncSession,
    *,
    buyer_character_name: str,
    buyer_character_id: int | None,
    type_id: int | None,
    type_name: str,
    quantity: int,
    unit_price_isk: float,
    delivery_location: str,
    notes: str = "",
) -> dict:
    tid = type_id
    tname = type_name.strip()
    if tid:
        row = await get_type(session, tid)
        if row:
            tname = row["name"]
    elif tname:
        row = await lookup_type_by_name(session, tname)
        if row:
            tid = row["type_id"]
            tname = row["name"]

    if not tid or quantity < 1 or unit_price_isk <= 0:
        return {"error": "invalid_order", "message": "Type, quantity, and price are required."}

    total = Decimal(str(unit_price_isk)) * quantity
    order = CorpMarketOrder(
        buyer_character_name=buyer_character_name.strip(),
        buyer_character_id=buyer_character_id or 0,
        type_id=tid,
        type_name=tname,
        quantity=quantity,
        unit_price_isk=Decimal(str(unit_price_isk)),
        total_price_isk=total,
        delivery_location=delivery_location.strip(),
        notes=notes.strip(),
        status="pending",
    )
    session.add(order)
    await session.flush()

    mail_subject = f"Corp Market order #{order.id} — {tname}"
    mail_body = (
        f"Corp Market order #{order.id}\n\n"
        f"Buyer: {order.buyer_character_name}\n"
        f"Item: {tname} x{quantity:,}\n"
        f"Unit price: {unit_price_isk:,.2f} ISK\n"
        f"Total: {float(total):,.2f} ISK\n"
        f"Deliver to: {order.delivery_location}\n"
    )
    if notes.strip():
        mail_body += f"\nNotes: {notes.strip()}\n"
    mail_body += (
        f"\nReply in-game to confirm. We will create an item exchange contract once approved.\n"
        f"— {settings.app_name}"
    )

    buyer_mail_ok = False
    buyer_mail_error = ""
    if buyer_character_id:
        buyer_mail_ok, buyer_mail_error = await send_character_mail(
            session,
            recipient_character_id=buyer_character_id,
            subject=mail_subject,
            body=mail_body,
        )

    corp_mail_ok = False
    corp_mail_error = ""
    notify_id = settings.corp_market_notify_character_id
    if notify_id:
        corp_mail_ok, corp_mail_error = await send_character_mail(
            session,
            recipient_character_id=int(notify_id),
            subject=f"[Staff] {mail_subject}",
            body=mail_body,
        )

    order.mail_sent_buyer = buyer_mail_ok
    order.mail_sent_corp = corp_mail_ok
    order.mail_error = "; ".join(filter(None, [buyer_mail_error, corp_mail_error]))[:2000]

    return {
        "id": order.id,
        "status": order.status,
        "type_id": order.type_id,
        "type_name": order.type_name,
        "quantity": order.quantity,
        "unit_price_isk": float(order.unit_price_isk),
        "total_price_isk": float(order.total_price_isk),
        "delivery_location": order.delivery_location,
        "mail_sent_buyer": buyer_mail_ok,
        "mail_sent_corp": corp_mail_ok,
        "mail_error": order.mail_error or None,
    }
