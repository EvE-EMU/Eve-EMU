"""Corp wallet journal polling for rental payments."""

from __future__ import annotations

import logging
import os
import re
from typing import Any

from django.utils import timezone

from .discord_notify import send_payment_webhook
from .models import MoonLease, RentalModuleSettings

logger = logging.getLogger(__name__)

WALLET_SCOPES = [
    "esi-wallet.read_corporation_wallets.v1",
    "esi-corporations.read_divisions.v1",
]


def _resolve_corp_token(settings: RentalModuleSettings):
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
        Token.objects.filter(
            character__corporation_id=settings.corporation_id,
        )
        .require_scopes(WALLET_SCOPES)
        .first()
    )


def _normalize_ref(text: str) -> str:
    return re.sub(r"\s+", " ", (text or "").strip().lower())


def poll_wallet_payments() -> dict[str, int]:
    """Match corp wallet journal entries to open leases."""
    settings = RentalModuleSettings.load()
    token = _resolve_corp_token(settings)
    if not token:
        logger.warning("moonrentals: no corp token for wallet journal")
        return {"matched": 0, "examined": 0, "error": 1}

    from pathlib import Path

    from esi.openapi_clients import ESIClientProvider

    from moonmining import __version__

    spec_file = Path(__file__).resolve().parents[1] / "openapi_2025-12-16.json"
    wallet_esi = ESIClientProvider(
        compatibility_date="2025-12-16",
        ua_appname="aa-moonmining-rentals",
        ua_version=__version__,
        operations=["GetCorporationsCorporationIdWalletsDivisionJournal"],
        spec_file=spec_file,
    )

    corp_id = int(settings.corporation_id)
    division = int(settings.wallet_division)
    keyword = settings.payment_keyword.strip().lower()

    try:
        entries = wallet_esi.client.Wallet.GetCorporationsCorporationIdWalletsDivisionJournal(
            corporation_id=corp_id,
            division=division,
            token=token,
        ).result()
    except Exception:
        logger.exception("moonrentals: wallet journal fetch failed")
        return {"matched": 0, "examined": 0, "error": 1}

    if not isinstance(entries, list):
        entries = list(entries) if entries else []

    leases = list(
        MoonLease.objects.filter(
            status__in=(MoonLease.STATUS_ACTIVE, MoonLease.STATUS_GRACE)
        ).select_related("moon", "moon__eve_moon__eve_planet__eve_solar_system")
    )
    ref_map: dict[str, MoonLease] = {}
    for lease in leases:
        ref_map[_normalize_ref(lease.ensure_payment_reference())] = lease

    matched = 0
    examined = 0
    for entry in entries:
        examined += 1
        desc = getattr(entry, "description", None) or getattr(entry, "reason", "") or ""
        desc_norm = _normalize_ref(str(desc))
        if keyword and keyword not in desc_norm:
            continue
        amount = int(getattr(entry, "amount", 0) or 0)
        if amount <= 0:
            continue
        lease = ref_map.get(desc_norm)
        if lease is None:
            for ref, candidate in ref_map.items():
                if ref in desc_norm or desc_norm in ref:
                    lease = candidate
                    break
        if lease is None:
            continue
        if amount < int(lease.monthly_rent_isk):
            logger.info(
                "moonrentals: partial payment %s for %s",
                amount,
                lease.location_label,
            )
            continue
        if lease.payment_status != MoonLease.PAYMENT_PAID:
            lease.mark_paid()
            send_payment_webhook(lease, amount_isk=amount)
            matched += 1

    return {"matched": matched, "examined": examined, "error": 0}
