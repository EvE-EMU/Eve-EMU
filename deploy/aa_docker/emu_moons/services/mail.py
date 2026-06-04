"""Deliver invoices via ESI mail (sender: El Emu Moon Tzar)."""

from __future__ import annotations

import logging
import os

from django.utils import timezone

from emu_moons.models import EmuInvoice, EmuMoonsSettings

logger = logging.getLogger(__name__)

MAIL_SCOPES = ["esi-mail.send_mail.v1"]


def _mail_sender_character_id(cfg: EmuMoonsSettings) -> int | None:
    if cfg.mail_sender_character_id:
        return int(cfg.mail_sender_character_id)
    raw = os.environ.get("AA_EMU_MOONS_MAIL_SENDER_CHARACTER_ID", "").strip()
    if raw.isdigit():
        return int(raw)
    return None


def _mail_token():
    cfg = EmuMoonsSettings.load()
    sender_id = _mail_sender_character_id(cfg)
    if not sender_id:
        return None
    from esi.models import Token

    return (
        Token.objects.filter(character_id=sender_id)
        .require_scopes(MAIL_SCOPES)
        .first()
    )


def send_invoice_mail(inv: EmuInvoice) -> bool:
    if inv.mail_sent_at:
        return True
    cfg = EmuMoonsSettings.load()
    token = _mail_token()
    if not token:
        sender_id = _mail_sender_character_id(cfg)
        if sender_id:
            inv.mail_error = (
                f"Character {sender_id} has no ESI token with esi-mail.send_mail.v1 "
                "(re-login on auth with mail send scope)"
            )
        else:
            inv.mail_error = "No mail sender character configured (EmuMoonsSettings.mail_sender_character_id)"
        inv.save(update_fields=["mail_error"])
        return False

    body = (
        f"Moon mining tax invoice {inv.invoice_number}\n\n"
        f"Extraction #{inv.extraction.extraction_number} — {inv.extraction.moon_label}\n"
        f"System: {inv.extraction.system_name}\n"
        f"Tax due: {inv.total_due_isk:,.2f} ISK\n\n"
        f"Pay {cfg.tax_corp_name} with reason: {inv.invoice_number}\n"
    )
    try:
        from esi.clients import EsiClientProvider

        client = EsiClientProvider(token=token)
        client.client.PostCharactersCharacterIdMail.post_characters_character_id_mail(
            character_id=token.character_id,
            body={
                "approved_cost": 0,
                "body": body,
                "recipients": [{"recipient_id": inv.character_id, "recipient_type": "character"}],
                "subject": f"Moon Tax {inv.invoice_number}",
            },
        )
        inv.mail_sent_at = timezone.now()
        inv.mail_error = ""
        inv.save(update_fields=["mail_sent_at", "mail_error"])
        return True
    except Exception as exc:
        inv.mail_error = str(exc)[:2000]
        inv.save(update_fields=["mail_error"])
        logger.warning("emu_moons mail failed for %s: %s", inv.invoice_number, exc)
        return False
