import inspect
import json
import os

from allianceauth.eveonline.models import (
    EveAllianceInfo,
    EveCharacter,
    EveCorporationInfo,
)

_currentdir = os.path.dirname(os.path.abspath(inspect.getfile(inspect.currentframe())))


def _load_entities_data():
    with open(_currentdir + "/entities.json", "r", encoding="utf-8") as f:
        return json.load(f)


_entities_data = _load_entities_data()


def load_entities():
    for character_info in _entities_data.get("EveCharacter"):
        if character_info.get("alliance_id"):
            alliance, _ = EveAllianceInfo.objects.update_or_create(
                alliance_id=character_info.get("alliance_id"),
                defaults={
                    "alliance_name": character_info.get("alliance_name"),
                    "alliance_ticker": character_info.get("alliance_ticker"),
                    "executor_corp_id": character_info.get("corporation_id"),
                },
            )
        else:
            alliance = None

        corporation, _ = EveCorporationInfo.objects.update_or_create(
            corporation_id=character_info.get("corporation_id"),
            defaults={
                "corporation_name": character_info.get("corporation_name"),
                "corporation_ticker": character_info.get("corporation_ticker"),
                "member_count": 99,
                "alliance": alliance,
            },
        )

        EveCharacter.objects.update_or_create(
            character_id=character_info.get("character_id"),
            defaults={
                "character_name": character_info.get("character_name"),
                "corporation_id": corporation.corporation_id,
                "corporation_name": corporation.corporation_name,
                "corporation_ticker": corporation.corporation_ticker,
                "alliance_id": alliance.alliance_id if alliance else None,
                "alliance_name": alliance.alliance_name if alliance else "",
                "alliance_ticker": alliance.alliance_ticker if alliance else "",
            },
        )
