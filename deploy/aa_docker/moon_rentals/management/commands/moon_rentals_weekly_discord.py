from django.core.management.base import BaseCommand

from moon_rentals.discord import send_weekly_report
from moon_rentals.reporting import build_weekly_report


class Command(BaseCommand):
    help = "Build compliance data and post the weekly moon report to Discord."

    def add_arguments(self, parser):
        parser.add_argument(
            "--no-refresh",
            action="store_true",
            help="Skip ESI/mining refresh before building the report.",
        )

    def handle(self, *args, **options):
        data = build_weekly_report(refresh=not options["no_refresh"])
        if send_weekly_report(data):
            self.stdout.write(self.style.SUCCESS("Weekly moon report posted to Discord."))
        else:
            self.stderr.write(
                "Failed to post (check MOON_RENTALS_DISCORD_WEBHOOK_URL and logs)."
            )
