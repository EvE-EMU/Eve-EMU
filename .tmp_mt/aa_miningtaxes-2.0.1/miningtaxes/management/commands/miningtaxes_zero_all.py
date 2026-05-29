from django.contrib.auth.models import User
from django.core.management.base import BaseCommand

from ...models import Character, Stats


class Command(BaseCommand):
    help = "Zeros all taxes of all characters"

    def handle(self, *args, **options):
        s = Stats.load()
        s.calc_admin_main_json()
        data = s.get_admin_main_json()
        for d in data:
            user = User.objects.get(pk=d["user"])
            characters = Character.objects.owned_by_user(user)
            suitable = None
            for c in characters:
                if c.is_main:
                    suitable = c
                    break
                suitable = c
            suitable.give_credit(d["balance"], "credit")
        s.calc_admin_main_json()
