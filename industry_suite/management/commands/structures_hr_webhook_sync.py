"""Sync aa-structures HR Discord webhook from env (see deploy/aa_docker/structures_hr_webhook.py)."""

from django.core.management.base import BaseCommand


class Command(BaseCommand):
    help = (
        "Create/update the aa-structures HR webhook (AA_STRUCTURES_HR_DISCORD_WEBHOOK_URL) "
        "and remove HR notification types from catch-all webhooks."
    )

    def add_arguments(self, parser):
        parser.add_argument(
            "--dry-run",
            action="store_true",
            help="Show what would change without writing to the database.",
        )

    def handle(self, *args, **options):
        from structures_hr_webhook import sync_structures_hr_webhook

        result = sync_structures_hr_webhook(dry_run=options["dry_run"])
        self.stdout.write(str(result))
