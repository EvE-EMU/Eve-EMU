"""
Seed a CorpTools CharacterTitle row so it appears in Title filter admin.

CorpTools only creates CharacterTitle when ESI reports that title on an audited
character. Unassigned corp titles (Commander, Logistics, etc.) are missing until
someone with that title is on Auth and titles are synced.

Usage (aa-web, from repo root):

  docker compose cp deploy/aa_docker/scripts/corptools_seed_character_title.py aa-web:/tmp/
  docker compose exec aa-web python manage.py shell -c "exec(open('/tmp/corptools_seed_character_title.py').read()); seed(98799892, 'False Gods', 0, 'Commander')"

Prefer discovering title_id from ESI: assign the title in-game to any Charlink
character, then run update_character_titles for that character and read
Admin → CorpTools → Character titles (or query CharacterTitle).
"""

from __future__ import annotations

from corptools.models import CharacterTitle


def seed(
    corporation_id: int,
    corporation_name: str,
    title_id: int,
    title: str,
) -> CharacterTitle:
    obj, created = CharacterTitle.objects.update_or_create(
        corporation_id=corporation_id,
        title_id=title_id,
        defaults={
            "corporation_name": corporation_name,
            "title": title,
        },
    )
    action = "created" if created else "updated"
    print(f"{action}: {obj}")
    return obj
