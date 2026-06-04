"""Create missing CharacterAudits and queue mail sync for all mail-scoped tokens."""

from django.core.management.base import BaseCommand
from django.db.models import Exists, OuterRef

from allianceauth.eveonline.models import EveCharacter
from corptools.models.audits import CharacterAudit
from corptools.tasks.character import update_char_mail, update_character
from esi.models import Token


class Command(BaseCommand):
    help = (
        "Backfill CorpTools CharacterAudit rows and queue mail sync for every "
        "character with esi-mail.read_mail.v1."
    )

    def add_arguments(self, parser):
        parser.add_argument(
            "--create-audits",
            action="store_true",
            help="Create CharacterAudit for every character that has any ESI token.",
        )
        parser.add_argument(
            "--sync-mail",
            action="store_true",
            help="Queue update_char_mail (force_refresh) for all mail-scoped tokens.",
        )
        parser.add_argument(
            "--sync-active",
            action="store_true",
            help="Queue update_character (force_refresh) for all active CharacterAudits.",
        )
        parser.add_argument(
            "--stagger-seconds",
            type=int,
            default=5,
            help="Seconds between queued Celery tasks (default: 5).",
        )

    def handle(self, *args, **options):
        do_audits = options["create_audits"]
        do_mail = options["sync_mail"]
        do_active = options["sync_active"]
        stagger = max(0, options["stagger_seconds"])

        if not (do_audits or do_mail or do_active):
            do_audits = do_mail = True

        mail_cids = list(
            Token.objects.filter(scopes__name="esi-mail.read_mail.v1")
            .values_list("character_id", flat=True)
            .distinct()
        )
        audit_cids = set(
            CharacterAudit.objects.values_list("character__character_id", flat=True)
        )

        if do_audits:
            has_token = Token.objects.filter(character_id=OuterRef("character_id"))
            token_cids = (
                EveCharacter.objects.annotate(_tok=Exists(has_token))
                .filter(_tok=True)
                .values_list("character_id", flat=True)
            )
            created = 0
            for cid in token_cids:
                if cid in audit_cids:
                    continue
                try:
                    ch = EveCharacter.objects.get_character_by_id(cid)
                    CharacterAudit.objects.update_or_create(
                        character=ch, defaults={"active": True}
                    )
                    audit_cids.add(cid)
                    created += 1
                except Exception as exc:
                    self.stderr.write(f"skip {cid}: {exc}")
            self.stdout.write(self.style.SUCCESS(f"Created {created} CharacterAudit row(s)."))

        if do_mail:
            queued = 0
            for i, cid in enumerate(mail_cids):
                update_char_mail.apply_async(
                    args=[cid],
                    kwargs={"force_refresh": True},
                    countdown=i * stagger,
                    priority=6,
                )
                queued += 1
            self.stdout.write(
                self.style.SUCCESS(f"Queued mail sync for {queued} character(s).")
            )

        if do_active:
            active_cids = list(
                CharacterAudit.objects.filter(active=True).values_list(
                    "character__character_id", flat=True
                )
            )
            for i, cid in enumerate(active_cids):
                update_character.apply_async(
                    args=[cid],
                    kwargs={"force_refresh": True},
                    countdown=i * stagger,
                    priority=5,
                )
            self.stdout.write(
                self.style.SUCCESS(
                    f"Queued full audit refresh for {len(active_cids)} active character(s)."
                )
            )

        with_mail = CharacterAudit.objects.filter(
            last_update_mails__isnull=False
        ).count()
        missing_scope = (
            CharacterAudit.objects.filter(active=True, last_update_mails__isnull=True)
            .exclude(character__character_id__in=mail_cids)
            .count()
        )
        self.stdout.write(f"Audits with mail timestamp: {with_mail}")
        self.stdout.write(
            f"Active audits still needing Charlink mail scope: {missing_scope}"
        )
