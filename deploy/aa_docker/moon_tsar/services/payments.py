"""Match corp wallet donations to open tax bills."""

from __future__ import annotations

import logging
import os
from decimal import Decimal

from django.db import transaction
from django.utils import timezone

from moon_tsar.models import MoonTaxBill, MoonTaxPayment, MoonTsarSettings

logger = logging.getLogger(__name__)


WALLET_SCOPES = [
    "esi-wallet.read_corporation_wallets.v1",
    "esi-corporations.read_divisions.v1",
]


def _corp_token():
    settings = MoonTsarSettings.load()
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
    return (
        Token.objects.filter(character__corporation_id=settings.corporation_id)
        .require_scopes(WALLET_SCOPES)
        .first()
    )


@transaction.atomic
def apply_wallet_payment(bill: MoonTaxBill, amount: Decimal, external_id: str, note: str) -> None:
    MoonTaxPayment.objects.create(
        bill=bill,
        source=MoonTaxPayment.SOURCE_WALLET,
        amount_isk=amount,
        external_id=external_id,
        note=note[:512],
    )
    bill.amount_paid_isk += amount
    if bill.amount_paid_isk >= bill.total_tax_isk:
        bill.status = MoonTaxBill.STATUS_PAID
        bill.paid_at = timezone.now()
    elif bill.amount_paid_isk > 0:
        bill.status = MoonTaxBill.STATUS_PARTIAL
    bill.save(update_fields=["amount_paid_isk", "status", "paid_at"])


def poll_wallet_tax_payments() -> int:
    settings = MoonTsarSettings.load()
    token = _corp_token()
    if not token:
        logger.warning("moon_tsar: no corp wallet token for tax payment poll")
        return 0

    try:
        from esi.clients import EsiClientProvider

        client = EsiClientProvider(token=token)
        journal = client.client.Wallet.get_corporations_corporation_id_wallets_division_journal(
            corporation_id=settings.corporation_id,
            division=settings.wallet_division,
        ).results()
    except Exception:
        logger.exception("moon_tsar wallet journal poll failed")
        return 0

    phrase = settings.tax_payment_phrase.upper()
    matched = 0
    open_bills = {
        b.payment_reference.upper(): b
        for b in MoonTaxBill.objects.filter(
            status__in=(MoonTaxBill.STATUS_OPEN, MoonTaxBill.STATUS_PARTIAL)
        )
    }

    for entry in journal or []:
        reason = (getattr(entry, "description", None) or getattr(entry, "reason", None) or "")
        if phrase not in reason.upper():
            continue
        ref_id = str(getattr(entry, "id", "") or "")
        if MoonTaxPayment.objects.filter(source=MoonTaxPayment.SOURCE_WALLET, external_id=ref_id).exists():
            continue
        amount = Decimal(str(abs(getattr(entry, "amount", 0) or 0)))
        bill = None
        upper = reason.upper()
        for ref, candidate in open_bills.items():
            if ref in upper:
                bill = candidate
                break
        if not bill:
            continue
        apply_wallet_payment(bill, amount, ref_id, reason)
        matched += 1
    return matched
