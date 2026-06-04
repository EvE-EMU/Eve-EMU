"""Delete and regenerate invoice(s) for an extraction (no mail/Discord)."""

from django.core.management.base import BaseCommand, CommandError

from emu_moons.models import EmuExtraction, EmuInvoice
from emu_moons.services.invoices import generate_invoices_for_extraction


class Command(BaseCommand):
    help = "Rebuild invoice(s) for an extraction using current moon-ore rules."

    def add_arguments(self, parser):
        parser.add_argument(
            "--invoice",
            help="Single invoice number to rebuild (uses its extraction).",
        )
        parser.add_argument(
            "--extraction-id",
            type=int,
            help="EmuExtraction PK to rebuild all invoices for.",
        )

    def handle(self, *args, **options):
        if options.get("invoice"):
            inv = EmuInvoice.objects.select_related("extraction").get(
                invoice_number__iexact=options["invoice"]
            )
            extraction = inv.extraction
            inv.lines.all().delete()
            inv.delete()
        elif options.get("extraction_id"):
            extraction = EmuExtraction.objects.get(pk=options["extraction_id"])
            deleted, _ = extraction.invoices.all().delete()
            self.stdout.write(f"Deleted {deleted} invoice(s).")
        else:
            raise CommandError("Provide --invoice or --extraction-id")

        extraction.invoices_generated = False
        extraction.invoices_generated_at = None
        extraction.discord_complete_sent = False
        extraction.save(
            update_fields=[
                "invoices_generated",
                "invoices_generated_at",
                "discord_complete_sent",
            ]
        )
        n = generate_invoices_for_extraction(extraction)
        self.stdout.write(self.style.SUCCESS(f"Created {n} invoice(s)."))
