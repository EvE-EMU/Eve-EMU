"""Ingest wallet journal and mining ledger for monthly KPIs."""

from __future__ import annotations

import logging
from datetime import datetime
from decimal import Decimal

from django.utils import timezone
from django.utils.dateparse import parse_datetime

from standing_fleet_tracker import app_settings
from standing_fleet_tracker.models import MiningLedgerEntry, WalletJournalEntry
from standing_fleet_tracker.services import esi as esi_api
from standing_fleet_tracker.services.fleet_activity import fleet_flags_at
from standing_fleet_tracker.services.scopes import missing_scopes_for_token

logger = logging.getLogger(__name__)


def ingest_wallet_journal(character, token) -> int:
    if app_settings.SFT_WALLET_SCOPE in missing_scopes_for_token(token):
        return 0
    rows = esi_api.get_character_wallet_journal(character.character_id, token)
    if not rows:
        return 0
    created = 0
    ratting_types = set(app_settings.SFT_RATTING_REF_TYPES)
    for row in rows[-500:]:
        ref_type = str(row.get("ref_type") or "")
        if ref_type not in ratting_types:
            continue
        journal_id = int(row["id"])
        if WalletJournalEntry.objects.filter(character=character, journal_id=journal_id).exists():
            continue
        when = parse_datetime(str(row.get("date") or "")) or timezone.now()
        in_fleet, in_standing = fleet_flags_at(character, when)
        WalletJournalEntry.objects.create(
            character=character,
            journal_id=journal_id,
            ref_type=ref_type,
            amount=Decimal(str(row.get("amount") or 0)),
            description=str(row.get("description") or "")[:512],
            recorded_at=when,
            in_fleet=in_fleet,
            in_standing_fleet=in_standing,
        )
        created += 1
    return created


def ingest_mining_ledger(character, token) -> int:
    if app_settings.SFT_MINING_SCOPE in missing_scopes_for_token(token):
        return 0
    rows = esi_api.get_character_mining_ledger(character.character_id, token)
    if not rows:
        return 0
    created = 0
    for row in rows:
        ledger_date = datetime.strptime(str(row["date"])[:10], "%Y-%m-%d").date()
        type_id = int(row["type_id"])
        solar_system_id = int(row["solar_system_id"])
        quantity = int(row["quantity"])
        when = timezone.make_aware(datetime.combine(ledger_date, datetime.min.time()))
        in_fleet, in_standing = fleet_flags_at(character, when)
        _, was_created = MiningLedgerEntry.objects.get_or_create(
            character=character,
            ledger_date=ledger_date,
            type_id=type_id,
            solar_system_id=solar_system_id,
            defaults={
                "quantity": quantity,
                "in_fleet": in_fleet,
                "in_standing_fleet": in_standing,
            },
        )
        if was_created:
            created += 1
    return created
