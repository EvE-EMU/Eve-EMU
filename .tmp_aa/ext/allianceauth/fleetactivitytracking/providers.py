import logging
from typing import TYPE_CHECKING

from esi.models import Token
from esi.openapi_clients import ESIClientProvider

from .. import __title__, __url__, __version__
from . import __esi_compatibility_date__

logger = logging.getLogger(__name__)

if TYPE_CHECKING:
    from esi.stubs import (
        CharactersCharacterIdLocationGet, CharactersCharacterIdOnlineGet,
        CharactersCharacterIdShipGet, UniverseStationsStationIdGet,
        UniverseStructuresStructureIdGet, UniverseSystemsSystemIdGet,
        UniverseTypesTypeIdGet,
    )

esi = ESIClientProvider(
    ua_appname=__title__,
    ua_version=__version__,
    ua_url=__url__,
    compatibility_date=__esi_compatibility_date__,
    operations=[
        "GetCharactersCharacterIdOnline",
        "GetCharactersCharacterIdLocation",
        "GetCharactersCharacterIdShip",
        "GetUniverseSystemsSystemId",
        "GetUniverseStationsStationId",
        "GetUniverseStructuresStructureId",
        "GetUniverseTypesTypeId",
    ])


def get_characters_character_id_online(character_id: int, token: Token) -> "CharactersCharacterIdOnlineGet":
    return esi.client.Location.GetCharactersCharacterIdOnline(character_id=character_id, token=token).result(use_etag=False)


def get_characters_character_id_location(character_id: int, token: Token) -> "CharactersCharacterIdLocationGet":
    return esi.client.Location.GetCharactersCharacterIdLocation(character_id=character_id, token=token).result(use_etag=False)


def get_characters_character_id_ship(character_id: int, token: Token) -> "CharactersCharacterIdShipGet":
    return esi.client.Location.GetCharactersCharacterIdShip(character_id=character_id, token=token).result(use_etag=False)


def get_universe_systems_system_id(system_id: int) -> "UniverseSystemsSystemIdGet":
    return esi.client.Universe.GetUniverseSystemsSystemId(system_id=system_id).result(use_etag=False)


def get_universe_stations_station_id(station_id: int) -> "UniverseStationsStationIdGet":
    return esi.client.Universe.GetUniverseStationsStationId(station_id=station_id).result(use_etag=False)


def get_universe_structures_structure_id(structure_id: int, token: Token) -> "UniverseStructuresStructureIdGet":
    return esi.client.Universe.GetUniverseStructuresStructureId(structure_id=structure_id, token=token).result(use_etag=False)


def get_universe_types_type_id(type_id: int) -> "UniverseTypesTypeIdGet":
    return esi.client.Universe.GetUniverseTypesTypeId(type_id=type_id).result(use_etag=False)
