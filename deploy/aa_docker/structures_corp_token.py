"""Pin aa-structures Owner ESI sync to specific django-esi tokens (private server).

Same env as CorpTools: ``AA_FALSE_GODS_CORP_TOKEN_ID`` / ``AA_CORP_TOKEN_OVERRIDES``.
"""

from __future__ import annotations

import logging

from corptools_corp_token import FALSE_GODS_CORP_ID, _parse_corp_token_overrides

logger = logging.getLogger(__name__)


def patch_structures_fetch_token() -> None:
    overrides = _parse_corp_token_overrides()
    if not overrides:
        return

    try:
        from esi.models import Token
        from structures.models import Owner
    except Exception:
        logger.exception("structures_corp_token: imports failed")
        return

    _orig = Owner.fetch_token

    def fetch_token(self, rotate_characters=None, ignore_schedule=False):
        corp_id = int(self.corporation.corporation_id)
        token_pk = overrides.get(corp_id)
        if token_pk is not None:
            token = (
                Token.objects.filter(pk=token_pk)
                .require_scopes(Owner.esi_scopes())
                .require_valid()
                .first()
            )
            if token:
                logger.debug(
                    "structures token override corp=%s token_pk=%s",
                    corp_id,
                    token_pk,
                )
                return token
            logger.warning(
                "structures token override missing scopes/valid corp=%s token_pk=%s",
                corp_id,
                token_pk,
            )
        return _orig(
            self,
            rotate_characters=rotate_characters,
            ignore_schedule=ignore_schedule,
        )

    Owner.fetch_token = fetch_token  # type: ignore[method-assign]
    logger.info("structures_corp_token: overrides active %s", overrides)


def ensure_structure_owners_from_overrides() -> None:
    """Create Owner + sync character for each corp in AA_CORP_TOKEN_OVERRIDES."""
    overrides = _parse_corp_token_overrides()
    if not overrides:
        return

    try:
        from django.db import transaction

        from allianceauth.authentication.models import CharacterOwnership
        from allianceauth.eveonline.models import EveCharacter, EveCorporationInfo
        from esi.models import Token
        from structures.models import Owner
        from structures.tasks import update_all_for_owner
    except Exception:
        logger.exception("structures bootstrap: imports failed")
        return

    for corp_id, token_pk in overrides.items():
        try:
            token = Token.objects.filter(pk=token_pk).first()
            if not token:
                logger.warning("structures bootstrap: token %s missing", token_pk)
                continue

            char = EveCharacter.objects.filter(character_id=token.character_id).first()
            if not char:
                logger.warning(
                    "structures bootstrap: EveCharacter %s missing",
                    token.character_id,
                )
                continue
            if int(char.corporation_id) != int(corp_id):
                logger.warning(
                    "structures bootstrap: token %s char corp %s != %s",
                    token_pk,
                    char.corporation_id,
                    corp_id,
                )
                continue

            ownership = CharacterOwnership.objects.filter(
                character__character_id=token.character_id
            ).first()
            if not ownership:
                logger.warning(
                    "structures bootstrap: no CharacterOwnership for char %s",
                    token.character_id,
                )
                continue

            try:
                corporation = EveCorporationInfo.objects.get(corporation_id=corp_id)
            except EveCorporationInfo.DoesNotExist:
                corporation = EveCorporationInfo.objects.create_corporation(corp_id)

            with transaction.atomic():
                owner, created = Owner.objects.update_or_create(
                    corporation=corporation,
                    defaults={"is_active": True},
                )
                owner.add_character(ownership)

            logger.info(
                "structures bootstrap: owner for corp %s (%s), created=%s",
                corp_id,
                corporation.corporation_name,
                created,
            )
            needs_sync = created or (
                owner.is_active and not owner.structures.exists()
            )
            if needs_sync:
                update_all_for_owner.delay(owner_pk=owner.pk)
        except Exception:
            logger.exception("structures bootstrap failed corp=%s", corp_id)
