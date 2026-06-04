from datetime import date

from django.core.management.base import BaseCommand
from django.db import transaction

from emu_moons.models import EmuExtraction, EmuInvoice, EmuMoonsSettings


class Command(BaseCommand):
    help = (
        "Void moon tax invoices and clear penalties before tax_effective_date "
        "(default 2026-06-01). Use --delete to remove rows instead of voiding."
    )

    def add_arguments(self, parser):
        parser.add_argument(
            "--before",
            type=str,
            default="",
            help="YYYY-MM-DD cutoff (default: EmuMoonsSettings.tax_effective_date).",
        )
        parser.add_argument(
            "--delete",
            action="store_true",
            help="Delete invoices/lines instead of marking void.",
        )

    def handle(self, *args, **options):
        cfg = EmuMoonsSettings.load()
        if options["before"]:
            y, m, d = options["before"].split("-")
            cutoff = date(int(y), int(m), int(d))
        else:
            cutoff = cfg.tax_effective_date

        inv_qs = EmuInvoice.objects.filter(issued_at__date__lt=cutoff)
        ext_qs = EmuExtraction.objects.filter(popped_at__date__lt=cutoff)

        inv_count = inv_qs.count()
        ext_count = ext_qs.count()

        with transaction.atomic():
            if options["delete"]:
                inv_qs.delete()
                self.stdout.write(self.style.WARNING(f"Deleted {inv_count} invoice(s)."))
            else:
                updated = inv_qs.exclude(status=EmuInvoice.STATUS_VOID).update(
                    status=EmuInvoice.STATUS_VOID,
                    penalty_isk=0,
                )
                self.stdout.write(
                    self.style.SUCCESS(f"Voided {updated} invoice(s) (of {inv_count} before cutoff).")
                )

        self.stdout.write(
            f"Cutoff {cutoff}: {ext_count} extraction(s) before date remain in DB "
            "(historical); new tax only applies from cutoff onward."
        )
