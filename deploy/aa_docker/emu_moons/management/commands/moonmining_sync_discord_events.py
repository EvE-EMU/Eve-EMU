"""Sync upcoming moonmining extractions to Discord guild scheduled events."""

from django.core.management.base import BaseCommand


class Command(BaseCommand):
    help = (
        "Create Discord guild scheduled events for upcoming moonmining extractions. "
        "Skips events that already exist (same title + start time)."
    )

    def add_arguments(self, parser):
        parser.add_argument(
            "--dry-run",
            action="store_true",
            help="List what would be created without calling Discord.",
        )

    def handle(self, *args, **options):
        from moonmining_discord_events import sync_extractions_to_discord

        result = sync_extractions_to_discord(dry_run=options["dry_run"])
        for line in result.messages or []:
            self.stdout.write(line)
        self.stdout.write(
            self.style.SUCCESS(
                f"Examined {result.examined}; created {result.created}; "
                f"skipped {result.skipped}; errors {result.errors}"
            )
        )
        if result.errors:
            raise SystemExit(2)
