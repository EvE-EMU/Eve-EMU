"""Seed default tax rates and settings singleton."""

from django.core.management.base import BaseCommand

from emu_moons.models import EmuMoonsSettings
from emu_moons.services.moonmining_reports import sync_structure_profiles_from_refineries
from emu_moons.services.tax_rates import seed_default_tax_rates


class Command(BaseCommand):
    help = "Initialize EMU Moons settings and default tax rate table"

    def add_arguments(self, parser):
        parser.add_argument(
            "--no-profiles",
            action="store_true",
            help="Skip seeding StructureTaxProfile from moonmining refineries.",
        )

    def handle(self, *args, **options):
        EmuMoonsSettings.load()
        n = seed_default_tax_rates()
        profiles = 0
        if not options["no_profiles"]:
            profiles = sync_structure_profiles_from_refineries()
        self.stdout.write(
            self.style.SUCCESS(
                f"EMU Moons ready ({n} new tax rate rows, {profiles} new structure profiles)"
            )
        )
