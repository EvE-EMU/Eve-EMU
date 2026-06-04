"""Invoice numbering, generation, penalties."""

from __future__ import annotations

import logging
import re
from datetime import date, timedelta
from decimal import Decimal

from django.contrib.auth import get_user_model
from django.db import transaction
from django.utils import timezone

from emu_moons.models import (
    EmuExtraction,
    EmuInvoice,
    EmuInvoiceLine,
    EmuMoonsSettings,
    MoonRarity,
)
from emu_moons.services.extractions import sync_extraction_ledger
from emu_moons.services.moon_exclusions import extraction_is_taxable
from emu_moons.services.pricing import is_moon_ore_type_id, rarity_for_type_id
from emu_moons.services.tax_rates import tax_rate_percent

logger = logging.getLogger(__name__)
User = get_user_model()


def _iso_week_parts(when: date | None = None) -> tuple[int, int]:
    when = when or timezone.now().date()
    iso = when.isocalendar()
    return iso.year % 100, iso.week


def allocate_invoice_number(when: date | None = None) -> str:
    """Format MT-YYWW-XXXX (sequential per ISO week)."""
    yy, ww = _iso_week_parts(when)
    prefix = f"MT-{yy:02d}{ww:02d}-"
    last = (
        EmuInvoice.objects.filter(invoice_number__startswith=prefix)
        .order_by("-invoice_number")
        .values_list("invoice_number", flat=True)
        .first()
    )
    seq = 1
    if last:
        m = re.search(r"-(\d{4})$", last)
        if m:
            seq = int(m.group(1)) + 1
    return f"{prefix}{seq:04d}"


def _aggregate_ledger_by_type(ledger_lines) -> list[dict]:
    """Merge ledger rows by type_id; moon ores only."""
    by_type: dict[int, dict] = {}
    for ll in ledger_lines:
        if not is_moon_ore_type_id(ll.type_id):
            continue
        bucket = by_type.get(ll.type_id)
        if bucket is None:
            bucket = {
                "type_id": ll.type_id,
                "type_name": ll.type_name,
                "quantity": 0,
                "volume_m3": Decimal("0"),
                "gross_isk": Decimal("0"),
            }
            by_type[ll.type_id] = bucket
        bucket["quantity"] += int(ll.quantity or 0)
        bucket["volume_m3"] += Decimal(str(ll.volume_m3 or 0))
        bucket["gross_isk"] += Decimal(str(ll.gross_isk or 0))
    return list(by_type.values())


def grouped_invoice_lines_for_display(invoice: EmuInvoice) -> list[dict]:
    """Invoice table rows: moon ores only, one line per type_id."""
    by_type: dict[int, dict] = {}
    for line in invoice.lines.all().order_by("ore_name", "type_id"):
        if not is_moon_ore_type_id(line.type_id):
            continue
        bucket = by_type.get(line.type_id)
        if bucket is None:
            rarity = line.moon_rarity or MoonRarity.UNKNOWN
            try:
                rarity_label = MoonRarity(rarity).label
            except ValueError:
                rarity_label = rarity
            bucket = {
                "type_id": line.type_id,
                "ore_name": line.ore_name,
                "moon_rarity": rarity,
                "rarity_display": rarity_label,
                "quantity": 0,
                "material_value_isk": Decimal("0"),
                "tax_rate_percent": line.tax_rate_percent,
                "tax_due_isk": Decimal("0"),
            }
            by_type[line.type_id] = bucket
            bucket["quantity"] += int(line.quantity or 0)
        bucket["material_value_isk"] += Decimal(str(line.material_value_isk or 0))
        bucket["tax_due_isk"] += Decimal(str(line.tax_due_isk or 0))
    for bucket in by_type.values():
        qty = bucket["quantity"]
        bucket["unit_value_isk"] = (
            (bucket["material_value_isk"] / qty).quantize(Decimal("0.01"))
            if qty
            else Decimal("0")
        )
    return sorted(by_type.values(), key=lambda r: r["ore_name"])


def weeks_late_penalty(original: Decimal, due_date: date, cfg: EmuMoonsSettings) -> Decimal:
    days = (timezone.now().date() - due_date).days
    if days <= cfg.grace_days_before_penalty:
        return Decimal("0")
    weeks = (days - cfg.grace_days_before_penalty) // 7
    return original * cfg.penalty_rate_per_week * Decimal(weeks)


@transaction.atomic
def generate_invoices_for_extraction(
    extraction: EmuExtraction,
    *,
    sync_ledger: bool = True,
    sync_ledger_fn=None,
) -> int:
    if not extraction_is_taxable(extraction):
        extraction.invoices_generated = True
        extraction.invoices_generated_at = timezone.now()
        extraction.save(update_fields=["invoices_generated", "invoices_generated_at"])
        return 0

    cfg = EmuMoonsSettings.load()
    if extraction.popped_at.date() < cfg.tax_effective_date:
        return 0

    if sync_ledger:
        if sync_ledger_fn is not None:
            sync_ledger_fn(extraction)
        else:
            sync_extraction_ledger(extraction)
    due = max(timezone.now().date(), cfg.tax_effective_date)

    by_character: dict[int, dict] = {}
    for line in extraction.ledger_lines.all():
        if not line.user_id:
            continue
        cid = int(line.miner_character_id)
        bucket = by_character.setdefault(
            cid,
            {
                "user": line.user,
                "character_id": cid,
                "character_name": line.miner_character_name or "",
                "lines": [],
            },
        )
        bucket["lines"].append(line)

    created = 0
    for cid, data in by_character.items():
        if EmuInvoice.objects.filter(
            extraction=extraction,
            character_id=cid,
        ).exclude(status=EmuInvoice.STATUS_VOID).exists():
            continue
        inv_lines: list[EmuInvoiceLine] = []
        total_tax = Decimal("0")
        total_vol = Decimal("0")
        for agg in _aggregate_ledger_by_type(data["lines"]):
            rarity = rarity_for_type_id(agg["type_id"])
            if rarity == MoonRarity.UNKNOWN:
                continue
            rate = tax_rate_percent(extraction.structure_class, rarity)
            if rate <= 0:
                continue
            mat_val = agg["gross_isk"].quantize(Decimal("0.01"))
            tax = (mat_val * rate / Decimal("100")).quantize(Decimal("0.01"))
            if tax <= 0:
                continue
            inv_lines.append(
                EmuInvoiceLine(
                    type_id=agg["type_id"],
                    ore_name=agg["type_name"],
                    moon_rarity=rarity,
                    tax_rate_percent=rate,
                    quantity=agg["quantity"],
                    volume_m3=agg["volume_m3"],
                    material_value_isk=mat_val,
                    tax_due_isk=tax,
                )
            )
            total_tax += tax
            total_vol += agg["volume_m3"]

        if not inv_lines or total_tax <= 0:
            continue

        try:
            from allianceauth.eveonline.models import EveCharacter

            ec = EveCharacter.objects.filter(character_id=cid).first()
            corp_id = ec.corporation_id if ec else None
            corp_name = ec.corporation_name if ec else ""
        except Exception:
            corp_id, corp_name = None, ""

        inv = EmuInvoice.objects.create(
            invoice_number=allocate_invoice_number(),
            extraction=extraction,
            user=data["user"],
            character_id=data["character_id"],
            character_name=data["character_name"],
            corporation_id=corp_id,
            corporation_name=(corp_name or "")[:255],
            due_at=due,
            original_tax_isk=total_tax,
            total_volume_m3=total_vol,
        )
        for row in inv_lines:
            row.invoice = inv
        EmuInvoiceLine.objects.bulk_create(inv_lines)
        created += 1

    has_open_invoices = EmuInvoice.objects.filter(extraction=extraction).exclude(
        status=EmuInvoice.STATUS_VOID
    ).exists()

    if created > 0 or has_open_invoices:
        extraction.invoices_generated = True
        extraction.invoices_generated_at = timezone.now()
        extraction.save(update_fields=["invoices_generated", "invoices_generated_at"])
    elif not extraction.ledger_lines.exists():
        extraction.invoices_generated = False
        extraction.invoices_generated_at = None
        extraction.save(update_fields=["invoices_generated", "invoices_generated_at"])
    return created


def refresh_penalties() -> int:
    cfg = EmuMoonsSettings.load()
    updated = 0
    for inv in EmuInvoice.objects.filter(
        status__in=(EmuInvoice.STATUS_OPEN, EmuInvoice.STATUS_PARTIAL, EmuInvoice.STATUS_CORP_LIABLE),
        due_at__gte=cfg.tax_effective_date,
    ):
        pen = weeks_late_penalty(inv.original_tax_isk, inv.due_at, cfg)
        if pen != inv.penalty_isk:
            inv.penalty_isk = pen
            inv.save(update_fields=["penalty_isk"])
            updated += 1
        if (
            inv.days_overdue >= cfg.corp_liability_days
            and inv.status == EmuInvoice.STATUS_OPEN
        ):
            inv.status = EmuInvoice.STATUS_CORP_LIABLE
            inv.corp_liability_at = timezone.now()
            inv.save(update_fields=["status", "corp_liability_at"])
            updated += 1
    return updated
