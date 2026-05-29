from django.core.management.base import BaseCommand

from ...tasks import auto_add_chars


class Command(BaseCommand):
    help = "Runs auto adding of characters into the plugin"

    def handle(self, *args, **options):
        auto_add_chars()
