"""Mark extractions on tax-exempt moons as non-invoiced; void open invoices."""

from __future__ import annotations

from django.core.management.base import BaseCommand
from django.db import transaction
from django.utils import timezone

from emu_moons.models import EmuExtraction, EmuInvoice
from emu_moons.services.moon_exclusions import extraction_is_taxable


class Command(BaseCommand):
    help = "Void invoices and skip invoicing for tax-exempt corp moons."

    def add_arguments(self, parser):
        parser.add_argument("--dry-run", action="store_true")

    def handle(self, *args, **options):
        dry = options["dry_run"]
        voided = 0
        skipped = 0
        with transaction.atomic():
            for ext in EmuExtraction.objects.all().order_by("popped_at"):
                if extraction_is_taxable(ext):
                    continue
                skipped += 1
                invs = EmuInvoice.objects.filter(extraction=ext).exclude(
                    status=EmuInvoice.STATUS_VOID
                )
                if dry:
                    voided += invs.count()
                    continue
                voided += invs.update(status=EmuInvoice.STATUS_VOID)
                ext.invoices_generated = True
                ext.invoices_generated_at = timezone.now()
                ext.save(update_fields=["invoices_generated", "invoices_generated_at"])
        self.stdout.write(
            self.style.SUCCESS(
                f"{'Would void' if dry else 'Voided'} {voided} invoice(s); "
                f"{skipped} tax-exempt extraction(s) marked complete."
            )
        )
