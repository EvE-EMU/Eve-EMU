from django.core.management.base import BaseCommand

from ... import tasks
from ...models import AdminCharacter, Character


class Command(BaseCommand):
    help = "Runs daily update manually"

    def handle(self, *args, **options):
        print("Beginning price update")
        tasks.update_all_prices()

        print("Beginning admin character updates")
        characters = AdminCharacter.objects.all()
        for character in characters:
            tasks.update_admin_character(character_pk=character.id)

        print("Running character update in parallel")
        characters = Character.objects.all()
        for character in characters:
            tasks.update_character(character_pk=character.id)

        tasks.precalcs([1, 1])
