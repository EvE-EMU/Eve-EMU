"""Rebuild EMU Moons invoices from ledger (per character, per ore)."""

from __future__ import annotations

from django.core.management.base import BaseCommand
from django.db import transaction

from emu_moons.models import EmuExtraction, EmuInvoice, EmuMoonsSettings
from emu_moons.testing import TEST_MM_ID_BASE, TEST_MM_ID_SPAN, is_test_extraction
from emu_moons.services.extractions import sync_extraction_ledger
from emu_moons.services.invoices import generate_invoices_for_extraction


class Command(BaseCommand):
    help = (
        "Void invoices and regenerate from extraction ledgers using per-character "
        "mining attribution (fixes whole-pop / single-ore test invoice bugs)."
    )

    def add_arguments(self, parser):
        parser.add_argument(
            "--system",
            type=str,
            default="",
            help="Only extractions in this solar system prefix (e.g. 0TKF-6).",
        )
        parser.add_argument(
            "--all",
            action="store_true",
            help="Rebuild every extraction (default: only those with invoices_generated).",
        )
        parser.add_argument(
            "--include-test",
            action="store_true",
            help="Include synthetic test extractions (moonmining_extraction_id 8100000+).",
        )
        parser.add_argument(
            "--dry-run",
            action="store_true",
            help="Show counts only; do not write.",
        )

    def handle(self, *args, **options):
        cfg = EmuMoonsSettings.load()
        qs = EmuExtraction.objects.all().order_by("popped_at")
        if not options["all"]:
            qs = qs.filter(invoices_generated=True)
        if options["system"]:
            qs = qs.filter(system_name__icontains=options["system"].strip())

        ext_list = list(qs)
        if not options["include_test"]:
            ext_list = [e for e in ext_list if not is_test_extraction(e)]
        self.stdout.write(f"Extractions to rebuild: {len(ext_list)}")

        if options["dry_run"]:
            inv_count = EmuInvoice.objects.filter(extraction__in=ext_list).count()
            self.stdout.write(f"Would void {inv_count} invoice(s).")
            return

        voided = 0
        rebuilt = 0
        invoices_created = 0

        with transaction.atomic():
            for ext in ext_list:
                invs = list(
                    EmuInvoice.objects.filter(extraction=ext).exclude(
                        status=EmuInvoice.STATUS_VOID
                    )
                )
                for inv in invs:
                    inv.status = EmuInvoice.STATUS_VOID
                    inv.save(update_fields=["status"])
                    voided += 1

                ext.invoices_generated = False
                ext.invoices_generated_at = None
                ext.save(update_fields=["invoices_generated", "invoices_generated_at"])

                if ext.popped_at.date() < cfg.tax_effective_date:
                    continue

                sync_extraction_ledger(ext)
                n = generate_invoices_for_extraction(ext, sync_ledger=False)
                invoices_created += n
                rebuilt += 1

        self.stdout.write(
            self.style.SUCCESS(
                f"Voided {voided} invoice(s); rebuilt {rebuilt} extraction(s); "
                f"created {invoices_created} new invoice(s)."
            )
        )
