import logging
from typing import TYPE_CHECKING

from django.db import models

from . import providers

logger = logging.getLogger(__name__)

if TYPE_CHECKING:
    from allianceauth.eveonline.models import (
        EveAllianceInfo, EveCharacter, EveCorporationInfo,
    )


class EveCharacterProviderManager:
    @staticmethod
    def get_character(character_id: int, use_etag: bool = True) -> providers.Character:
        return providers.open_api_provider.get_character(character_id, use_etag=use_etag)


class EveCharacterManager(models.Manager):
    provider = EveCharacterProviderManager()

    def exclude_biomassed(self) -> "models.QuerySet[EveCharacter]":
        """
        Get a queryset of EveCharacter objects, excluding the "Doomheim" corporation (1000001).

        :return:
        :rtype:
        """

        return self.exclude(corporation_id=1000001)

    def create_character(self, character_id) -> "EveCharacter":
        return self.create_character_obj(self.provider.get_character(character_id, use_etag=False))  # ETAG False, We need response data to create a character object.

    def create_character_obj(self, character: providers.Character) -> "EveCharacter":
        return self.create(
            character_id=character.id,
            character_name=character.name,
            corporation_id=character.corp.id,
            corporation_name=character.corp.name,
            corporation_ticker=character.corp.ticker,
            alliance_id=character.alliance.id,
            alliance_name=character.alliance.name,
            alliance_ticker=getattr(character.alliance, 'ticker', None),
            faction_id=character.faction.id,
            faction_name=character.faction.name
        )

    def update_character(self, character_id) -> "EveCharacter":
        return self.get(character_id=character_id).update_character()

    def get_character_by_id(self, character_id: int) -> "EveCharacter | None":
        """Return character by character ID or None if not found."""
        try:
            return self.get(character_id=character_id)
        except self.model.DoesNotExist:
            return None


class EveAllianceProviderManager:
    @staticmethod
    def get_alliance(alliance_id, use_etag: bool = True) -> providers.Alliance:
        return providers.open_api_provider.get_alliance(alliance_id, use_etag=use_etag)

    @staticmethod
    def get_alliance_corps(alliance_id, use_etag: bool = True) -> list[int]:
        return providers.open_api_provider.get_alliance_corps(alliance_id, use_etag=use_etag)


class EveAllianceManager(models.Manager):
    provider = EveAllianceProviderManager()

    def create_alliance(self, alliance_id: int) -> "EveAllianceInfo":
        obj = self.create_alliance_obj(self.provider.get_alliance(alliance_id=alliance_id, use_etag=False))  # ETAG False, We need response data to create an alliance object.
        obj.populate_alliance()
        return obj

    def create_alliance_obj(self, alliance: providers.Alliance) -> "EveAllianceInfo":
        return self.create(
            alliance_id=alliance.id,
            alliance_name=alliance.name,
            alliance_ticker=alliance.ticker,
            executor_corp_id=alliance.executor_corp_id,
        )

    def update_alliance(self, alliance_id) -> "EveAllianceInfo":
        return self.get(alliance_id=alliance_id).update_alliance()


class EveCorporationProviderManager:
    @staticmethod
    def get_corporation(corp_id: int, use_etag: bool = True) -> providers.Corporation:
        return providers.open_api_provider.get_corp(corp_id, use_etag=use_etag)


class EveCorporationManager(models.Manager):
    provider = EveCorporationProviderManager()

    def create_corporation(self, corp_id: int, use_etag: bool = True) -> "EveCorporationInfo":
        return self.create_corporation_obj(self.provider.get_corporation(corp_id=corp_id, use_etag=use_etag))  # ETAG False, We need response data to create a corporation object.

    def create_corporation_obj(self, corp: providers.Corporation) -> "EveCorporationInfo":
        from .models import EveAllianceInfo
        try:
            alliance = EveAllianceInfo.objects.get(alliance_id=corp.alliance_id)
        except EveAllianceInfo.DoesNotExist:
            alliance = None
        return self.create(
            corporation_id=corp.id,
            corporation_name=corp.name,
            corporation_ticker=corp.ticker,
            member_count=corp.members,
            alliance=alliance,
        )

    def update_corporation(self, corp_id: int) -> "EveCorporationInfo":
        return self.get(corporation_id=corp_id).update_corporation()
