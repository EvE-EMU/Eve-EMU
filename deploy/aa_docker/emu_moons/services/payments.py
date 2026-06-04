"""Match corporation wallet journal entries to invoice numbers MT-YYWW-XXXX."""

from __future__ import annotations

import logging
import os
import re
from decimal import Decimal

from django.db import transaction
from django.utils import timezone

from emu_moons.models import EmuInvoice, EmuMoonsSettings

logger = logging.getLogger(__name__)

INVOICE_REF_RE = re.compile(r"MT-\d{4}-\d{4}", re.I)
MAIN_ACCOUNT_REF_RE = re.compile(r"MT-MAIN(\d+)EMU", re.I)
MAIN_ACCOUNT_LEGACY_RE = re.compile(r"MAIN-([A-Za-z0-9_]+)", re.I)

WALLET_SCOPES = [
    "esi-wallet.read_corporation_wallets.v1",
    "esi-corporations.read_divisions.v1",
]


def _corp_token():
    settings = EmuMoonsSettings.load()
    from esi.models import Token

    if settings.esi_token_id:
        token = (
            Token.objects.filter(pk=settings.esi_token_id)
            .require_scopes(WALLET_SCOPES)
            .first()
        )
        if token:
            return token
    override_pk = os.environ.get("AA_FALSE_GODS_CORP_TOKEN_ID", "").strip()
    if override_pk.isdigit():
        token = (
            Token.objects.filter(pk=int(override_pk))
            .require_scopes(WALLET_SCOPES)
            .first()
        )
        if token:
            return token
    try:
        from allianceauth.eveonline.models import EveCharacter

        char_ids = EveCharacter.objects.filter(
            corporation_id=settings.corporation_id
        ).values_list("character_id", flat=True)
        token = (
            Token.objects.filter(character_id__in=char_ids)
            .require_scopes(WALLET_SCOPES)
            .first()
        )
        if token:
            return token
    except Exception:
        pass
    return None


@transaction.atomic
def apply_payment(inv: EmuInvoice, amount: Decimal, tx_id: int, division: int, note: str) -> None:
    inv.amount_paid_isk += amount
    inv.wallet_transaction_id = tx_id
    inv.wallet_division = division
    if inv.amount_paid_isk >= inv.total_due_isk:
        inv.status = EmuInvoice.STATUS_PAID
        inv.paid_at = timezone.now()
    elif inv.amount_paid_isk > 0:
        inv.status = EmuInvoice.STATUS_PARTIAL
    inv.save(
        update_fields=[
            "amount_paid_isk",
            "status",
            "paid_at",
            "wallet_transaction_id",
            "wallet_division",
        ]
    )


def poll_wallet_payments() -> int:
    settings = EmuMoonsSettings.load()
    token = _corp_token()
    if not token:
        logger.warning("emu_moons: no corp wallet token for payment poll")
        return 0

    try:
        from esi.clients import EsiClientProvider

        client = EsiClientProvider(token=token)
        journal = client.client.Wallet.get_corporations_corporation_id_wallets_division_journal(
            corporation_id=settings.corporation_id,
            division=settings.wallet_division,
        ).results()
    except Exception:
        logger.exception("emu_moons wallet journal poll failed")
        return 0

    open_status = (
        EmuInvoice.STATUS_OPEN,
        EmuInvoice.STATUS_PARTIAL,
        EmuInvoice.STATUS_CORP_LIABLE,
    )
    open_invoices = {
        inv.invoice_number.upper(): inv
        for inv in EmuInvoice.objects.filter(status__in=open_status)
    }
    matched = 0
    for entry in journal or []:
        reason = (getattr(entry, "description", None) or getattr(entry, "reason", None) or "")
        tx_id = int(getattr(entry, "id", 0) or 0)
        amount = Decimal(str(abs(getattr(entry, "amount", 0) or 0)))
        if amount <= 0:
            continue

        m = INVOICE_REF_RE.search(reason)
        if m:
            ref = m.group(0).upper()
            inv = open_invoices.get(ref)
            if not inv:
                continue
            if tx_id and inv.wallet_transaction_id == tx_id:
                continue
            apply_payment(inv, amount, tx_id, settings.wallet_division, reason)
            matched += 1
            continue

        from django.contrib.auth import get_user_model

        from allianceauth.eveonline.models import EveCharacter

        user = None
        main_m = MAIN_ACCOUNT_REF_RE.search(reason)
        if main_m:
            char_id = int(main_m.group(1))
            user = (
                get_user_model()
                .objects.filter(profile__main_character__character_id=char_id)
                .first()
            )
            if not user:
                ownership = (
                    EveCharacter.objects.filter(character_id=char_id)
                    .select_related("character_ownership__user")
                    .first()
                )
                if ownership and hasattr(ownership, "character_ownership"):
                    user = ownership.character_ownership.user
        if not user:
            legacy = MAIN_ACCOUNT_LEGACY_RE.search(reason)
            if legacy:
                user = get_user_model().objects.filter(
                    username__iexact=legacy.group(1)
                ).first()
        if not user:
            continue
        user_invoices = [
            inv
            for inv in EmuInvoice.objects.filter(user=user, status__in=open_status).order_by(
                "due_at", "invoice_number"
            )
        ]
        remaining = amount
        for inv in user_invoices:
            if remaining <= 0:
                break
            due = inv.total_due_isk - inv.amount_paid_isk
            if due <= 0:
                continue
            chunk = min(remaining, due)
            apply_payment(inv, chunk, tx_id, settings.wallet_division, reason)
            remaining -= chunk
            matched += 1
    return matched
