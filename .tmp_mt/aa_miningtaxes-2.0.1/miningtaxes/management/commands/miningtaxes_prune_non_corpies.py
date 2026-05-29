from django.core.management.base import BaseCommand

from ...models import AdminCharacter, Character


class Command(BaseCommand):
    help = "Purges characters where their main is not in a tracked corp."

    def handle(self, *args, **options):
        alltoons = AdminCharacter.objects.all()
        validcorps = set()
        for char in alltoons:
            validcorps.add(char.eve_character.corporation_id)

        alltoons = Character.objects.all()

        for char in alltoons:
            try:
                cid = (
                    char.eve_character.character_ownership.user.profile.main_character.corporation_id
                )
            except Exception as e:
                print(f"Exception: {e}")
                char.delete()
                continue

            if cid not in validcorps:
                print(
                    f"Deleting {char.eve_character.character_name} - main: {char.eve_character.character_ownership.user.profile.main_character.character_name}"
                )
                char.delete()
