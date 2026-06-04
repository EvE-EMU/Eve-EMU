"""Patched Secure Groups beat setup — interval from AA_BEAT_SECUREGROUPS_MINUTES (default 30)."""

import os

from django.core.management.base import BaseCommand
from django_celery_beat.models import CrontabSchedule, PeriodicTask


def _beat_minutes() -> int:
    raw = os.environ.get("AA_BEAT_SECUREGROUPS_MINUTES", "30").strip()
    try:
        minutes = max(1, min(int(raw), 59))
    except ValueError:
        minutes = 30
    return minutes


class Command(BaseCommand):
    help = "Setup/Reset the Periodic Task for the Secure Groups module (eve-emu: default every 30 minutes)"

    def handle(self, *args, **options):
        minutes = _beat_minutes()
        cron_minute = f"*/{minutes}" if minutes < 60 else "0"
        self.stdout.write(
            f"Creating/Updating Secure Groups beat task (every {minutes} minute(s), UTC)"
        )
        schedule, _ = CrontabSchedule.objects.get_or_create(
            minute=cron_minute,
            hour="*",
            day_of_week="*",
            day_of_month="*",
            month_of_year="*",
            timezone="UTC",
        )
        PeriodicTask.objects.update_or_create(
            task="securegroups.tasks.run_smart_groups",
            defaults={
                "crontab": schedule,
                "name": "Secure Group Updater",
                "enabled": True,
            },
        )
        self.stdout.write(self.style.SUCCESS("Success!"))
