"""Consolidated moon tax statement per Alliance Auth account (all linked alts)."""

from __future__ import annotations

from decimal import Decimal

from django.contrib.auth import get_user_model

from emu_moons.models import EmuInvoice
from emu_moons.services.invoices import grouped_invoice_lines_for_display
from emu_moons.testing import is_test_extraction

User = get_user_model()


def wallet_reason_for_user(user) -> str:
    character_id = _main_character_id(user)
    if character_id is None:
        return "MT-MAIN0EMU"
    return f"MT-MAIN{character_id}EMU"


def _main_character_id(user) -> int | None:
    try:
        main = user.profile.main_character
        if main:
            return int(main.character_id)
    except Exception:
        pass
    inv = (
        EmuInvoice.objects.filter(user=user)
        .order_by("-issued_at")
        .values_list("character_id", flat=True)
        .first()
    )
    return int(inv) if inv else None


def _corp_display(user) -> str:
    try:
        main = user.profile.main_character
        if main and main.corporation_name:
            ticker = main.alliance_ticker or ""
            name = main.corporation_name
            return f"{name} [{ticker}]" if ticker else name
    except Exception:
        pass
    inv = EmuInvoice.objects.filter(user=user).order_by("-issued_at").first()
    if inv and inv.corporation_name:
        return inv.corporation_name
    return ""


def build_account_statement(
    user,
    *,
    highlight_invoice_number: str | None = None,
    include_paid: bool = False,
) -> dict:
    """All invoice sections for one AA user, grouped by extraction / character."""
    statuses = (
        EmuInvoice.STATUS_OPEN,
        EmuInvoice.STATUS_PARTIAL,
        EmuInvoice.STATUS_CORP_LIABLE,
    )
    if include_paid:
        statuses = (*statuses, EmuInvoice.STATUS_PAID)

    from emu_moons.access import tax_effective_date

    cutoff = tax_effective_date()
    invoices = list(
        EmuInvoice.objects.filter(user=user, status__in=statuses, due_at__gte=cutoff)
        .exclude(status=EmuInvoice.STATUS_VOID)
        .filter(issued_at__date__gte=cutoff)
        .select_related("extraction")
        .prefetch_related("lines")
        .order_by("-extraction__popped_at", "character_name", "invoice_number")
    )

    sections = []
    total_due = Decimal("0")
    total_penalty = Decimal("0")
    total_original = Decimal("0")

    for inv in invoices:
        if is_test_extraction(inv.extraction):
            continue
        lines = grouped_invoice_lines_for_display(inv)
        section_tax = sum((row["tax_due_isk"] for row in lines), Decimal("0"))
        if not lines:
            section_tax = inv.total_due_isk - inv.penalty_isk
        section_value = sum((row["material_value_isk"] for row in lines), Decimal("0"))
        total_due += inv.total_due_isk
        total_penalty += inv.penalty_isk
        total_original += inv.original_tax_isk
        sections.append(
            {
                "invoice": inv,
                "invoice_number": inv.invoice_number,
                "character_id": inv.character_id,
                "character_name": inv.character_name,
                "extraction": inv.extraction,
                "lines": lines,
                "section_tax_isk": section_tax if lines else inv.original_tax_isk,
                "section_value_isk": section_value,
                "highlight": bool(
                    highlight_invoice_number
                    and inv.invoice_number.upper()
                    == highlight_invoice_number.upper()
                ),
            }
        )

    return {
        "user": user,
        "username": user.username,
        "main_character_id": _main_character_id(user),
        "corporation_display": _corp_display(user),
        "wallet_reason": wallet_reason_for_user(user),
        "sections": sections,
        "invoice_count": len(sections),
        "total_due_isk": total_due,
        "total_penalty_isk": total_penalty,
        "total_original_isk": total_original,
        "highlight_invoice_number": highlight_invoice_number,
    }
