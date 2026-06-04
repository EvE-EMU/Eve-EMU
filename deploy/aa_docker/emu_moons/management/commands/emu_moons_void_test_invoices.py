"""Void open EMU Moons invoices tied to synthetic test extractions."""

from __future__ import annotations

from django.core.management.base import BaseCommand
from django.utils import timezone

from emu_moons.models import EmuInvoice
from emu_moons.testing import TEST_MM_ID_BASE, TEST_MM_ID_SPAN


class Command(BaseCommand):
    help = "Void non-paid invoices for emu_moons_test_invoices synthetic extractions."

    def add_arguments(self, parser):
        parser.add_argument(
            "--dry-run",
            action="store_true",
            help="Print count only.",
        )

    def handle(self, *args, **options):
        qs = EmuInvoice.objects.filter(
            extraction__moonmining_extraction_id__gte=TEST_MM_ID_BASE,
            extraction__moonmining_extraction_id__lt=TEST_MM_ID_BASE + TEST_MM_ID_SPAN,
        ).exclude(status=EmuInvoice.STATUS_VOID).exclude(status=EmuInvoice.STATUS_PAID)
        count = qs.count()
        if options["dry_run"]:
            self.stdout.write(f"Would void {count} invoice(s).")
            return
        updated = qs.update(status=EmuInvoice.STATUS_VOID)
        self.stdout.write(self.style.SUCCESS(f"Voided {updated} test invoice(s) at {timezone.now()}."))
