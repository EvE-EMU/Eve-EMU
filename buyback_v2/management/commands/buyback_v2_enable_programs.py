from django.core.management.base import BaseCommand

from buybackprogram.models import Program
from buyback_v2.models import ProgramPricingProfile


class Command(BaseCommand):
    help = "Create or refresh buyback v2 pricing profiles for all buyback programs."

    def handle(self, *args, **options):
        count = 0
        for program in Program.objects.all().iterator():
            ProgramPricingProfile.objects.get_or_create(program=program)
            count += 1
        self.stdout.write(self.style.SUCCESS(f"Ensured v2 pricing profiles for {count} program(s)."))
