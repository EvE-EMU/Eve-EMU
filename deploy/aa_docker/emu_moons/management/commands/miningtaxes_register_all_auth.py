"""Register all Alliance Auth characters in miningtaxes and refresh mining ledgers."""

from __future__ import annotations

from django.core.management.base import BaseCommand
from django.db import transaction
from esi.errors import TokenError
from esi.models import Token

from allianceauth.eveonline.models import EveCharacter
from miningtaxes.models import Character, Stats
from django.core.management import call_command


class Command(BaseCommand):
    help = (
        "Create miningtaxes Character rows for every AA character with a user "
        "and esi-industry.read_character_mining.v1, then refresh mining ledgers."
    )

    def add_arguments(self, parser):
        parser.add_argument(
            "--register-only",
            action="store_true",
            help="Only register characters; do not pull ledgers.",
        )
        parser.add_argument(
            "--skip-prices",
            action="store_true",
            help="Skip ore price refresh before ledger updates.",
        )
        parser.add_argument(
            "--force-ledger",
            action="store_true",
            help="Refresh ledger even when not stale.",
        )
        parser.add_argument(
            "--limit",
            type=int,
            default=0,
            help="Max characters to update (0 = all).",
        )

    def handle(self, *args, **options):
        scopes = Character.get_esi_scopes()
        register_only = options["register_only"]
        force_ledger = options["force_ledger"]
        limit = options["limit"]

        eve_chars = (
            EveCharacter.objects.filter(character_ownership__isnull=False)
            .distinct()
            .order_by("character_name")
        )

        added = 0
        already = 0
        skipped_no_token = 0
        skipped_orphan = 0

        for eve_char in eve_chars:
            try:
                eve_char.character_ownership.user
            except Exception:
                skipped_orphan += 1
                continue

            if not Token.get_token(eve_char.character_id, scopes):
                skipped_no_token += 1
                continue

            exists = Character.objects.filter(eve_character=eve_char).exists()
            with transaction.atomic():
                Character.objects.update_or_create(eve_character=eve_char)
            if exists:
                already += 1
            else:
                added += 1

        self.stdout.write(
            self.style.SUCCESS(
                f"Registered: {added} new, {already} existing, "
                f"{skipped_no_token} without mining token, {skipped_orphan} without user."
            )
        )
        self.stdout.write(f"Total miningtaxes characters: {Character.objects.count()}")

        if register_only:
            return

        if not options["skip_prices"]:
            self.stdout.write("Refreshing ore prices…")
            try:
                call_command("miningtaxes_preload_prices", verbosity=0)
            except Exception as exc:
                self.stdout.write(self.style.WARNING(f"Price update issue: {exc}"))

        qs = Character.objects.select_related("eve_character").order_by("id")
        total = qs.count()
        if limit > 0:
            qs = qs[:limit]
            total = min(total, limit)

        updated = 0
        skipped_stale = 0
        errors = 0

        for i, character in enumerate(qs, start=1):
            if character.is_orphan:
                continue
            if not force_ledger and not character.is_ledger_stale():
                skipped_stale += 1
                continue
            name = character.eve_character.character_name
            try:
                character.update_mining_ledger()
                updated += 1
                if i % 25 == 0 or i == total:
                    self.stdout.write(f"  [{i}/{total}] updated {name}")
            except TokenError:
                errors += 1
                self.stdout.write(self.style.WARNING(f"  TokenError: {name}"))
            except Exception as exc:
                errors += 1
                self.stdout.write(self.style.ERROR(f"  Failed {name}: {exc}"))

        self.stdout.write("Running precalc…")
        for character in Character.objects.all():
            try:
                character.precalc_all()
            except Exception:
                pass
        stats = Stats.load()
        stats.precalc_all()

        self.stdout.write(
            self.style.SUCCESS(
                f"Ledger refresh done: {updated} updated, "
                f"{skipped_stale} skipped (not stale), {errors} errors."
            )
        )
