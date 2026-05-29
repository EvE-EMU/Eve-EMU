"""Use ESI affiliation (not public character sheet) for corporation on emu servers."""

from __future__ import annotations

import logging

logger = logging.getLogger(__name__)

_patched = False


def patch_eve_character_update_from_affiliation() -> None:
    """Prefer PostCharactersAffiliation corp over GetCharactersCharacterId on eve-emu."""
    global _patched
    if _patched:
        return

    from allianceauth.eveonline.models import EveCharacter, EveCorporationInfo
    from allianceauth.eveonline.providers import open_api_provider

    _original = EveCharacter.update_character

    def update_character(self) -> EveCharacter:
        self = _original(self)
        try:
            affs = open_api_provider.get_affiliations(
                [self.character_id], force_refresh=True
            )
        except Exception:
            logger.warning(
                "Affiliation lookup failed for character %s",
                self.character_id,
                exc_info=True,
            )
            return self
        if not affs:
            return self

        aff = affs[0]
        corp_id = int(aff.corporation_id)
        if corp_id == self.corporation_id:
            return self

        try:
            corporation_obj = EveCorporationInfo.objects.get(corporation_id=corp_id)
        except EveCorporationInfo.DoesNotExist:
            corporation_obj = EveCorporationInfo.objects.create_corporation(
                corporation_id=corp_id
            )

        alliance_id = getattr(aff, "alliance_id", None)
        alliance_obj = None
        if alliance_id:
            from allianceauth.eveonline.models import EveAllianceInfo

            alliance_id = int(alliance_id)
            try:
                alliance_obj = EveAllianceInfo.objects.get(alliance_id=alliance_id)
            except EveAllianceInfo.DoesNotExist:
                alliance_obj = EveAllianceInfo.objects.create_alliance(
                    alliance_id=alliance_id
                )

        self.corporation_id = corp_id
        self.corporation_name = corporation_obj.corporation_name
        self.corporation_ticker = corporation_obj.corporation_ticker
        self.alliance_id = alliance_id
        self.alliance_name = alliance_obj.alliance_name if alliance_obj else ""
        self.alliance_ticker = alliance_obj.alliance_ticker if alliance_obj else ""
        self.save(
            update_fields=[
                "corporation_id",
                "corporation_name",
                "corporation_ticker",
                "alliance_id",
                "alliance_name",
                "alliance_ticker",
            ]
        )
        logger.info(
            "Corrected %s corporation from affiliation: corp_id=%s (%s)",
            self.character_name,
            corp_id,
            corporation_obj.corporation_name,
        )
        return self

    EveCharacter.update_character = update_character
    _patched = True
