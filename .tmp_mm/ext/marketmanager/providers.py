import typing
from typing import Literal

from httpx import Response

from allianceauth.services.hooks import get_extension_logger
from esi.models import Token
from esi.openapi_clients import ESIClientProvider

from . import __esi_compatibility_date__, __title__, __url__, __version__

if typing.TYPE_CHECKING:
    from esi.stubs import (
        CharacterID, CharactersCharacterIdOrdersGetItem,
        CharactersCharacterIdOrdersHistoryGetItem,
        CharactersCharacterIdRolesGet, CorporationsCorporationIdOrdersGetItem,
        CorporationsCorporationIdOrdersHistoryGetItem,
        CorporationsCorporationIdStructuresGetItem,
        MarketsRegionIdHistoryGetItem, MarketsRegionIdOrdersGetItem,
        MarketsStructuresStructureIdGetItem, UniverseStructuresStructureIdGet,
    )


logger = get_extension_logger(__name__)


esi = ESIClientProvider(
    compatibility_date=__esi_compatibility_date__,
    ua_appname=__title__,
    ua_version=__version__,
    ua_url=__url__,
    operations=[
        "GetUniverseStructures",
        "GetUniverseStructuresStructureId",
        "GetCharactersCharacterIdOrders",
        "GetCharactersCharacterIdOrdersHistory",
        "GetCharactersCharacterIdRoles",
        "GetCorporationsCorporationIdOrders",
        "GetCorporationsCorporationIdOrdersHistory",
        "GetCorporationsCorporationIdStructures",
        "GetMarketsRegionIdOrders"
    ]
)


def get_universe_structures(filter: Literal['market', 'manufacturing_basic']) -> list[int]:
    result = esi.client.Universe.GetUniverseStructures(
        filter=filter
    ).results()
    return result


def get_universe_structures_structure_id(structure_id: int, token: Token) -> "UniverseStructuresStructureIdGet":
    result = esi.client.Universe.GetUniverseStructuresStructureId(
        structure_id=structure_id,
        token=token
    ).result()
    return result


def get_markets_region_id_orders(region_id: int, order_type: Literal['buy', 'sell', 'all'] = 'all') -> list["MarketsRegionIdOrdersGetItem"]:
    results = esi.client.Market.GetMarketsRegionIdOrders(
        order_type=order_type,
        region_id=region_id
    ).results()
    return results


def get_markets_region_id_orders_paged(region_id: int, page: int, order_type: Literal['buy', 'sell', 'all'] = 'all') -> tuple[list["MarketsRegionIdOrdersGetItem"], Response]:
    result, response = esi.client.Market.GetMarketsRegionIdOrders(
        order_type=order_type,
        region_id=region_id,
        page=page
    ).result(return_response=True)
    return result, response


def get_markets_region_id_orders_by_typeid(region_id: int, order_type: Literal['buy', 'sell', 'all'] = 'all', type_id: int | None = None) -> list["MarketsRegionIdOrdersGetItem"]:
    result = esi.client.Market.GetMarketsRegionIdOrders(
        order_type=order_type,
        region_id=region_id,
        type_id=type_id
    ).results()
    return result


def get_markets_region_id_orders_by_typeid_paged(region_id: int, page: int, order_type: Literal['buy', 'sell', 'all'] = 'all', type_id: int | None = None) -> tuple[list["MarketsRegionIdOrdersGetItem"], Response]:
    result, response = esi.client.Market.GetMarketsRegionIdOrders(
        order_type=order_type,
        region_id=region_id,
        type_id=type_id,
        page=page
    ).result(return_response=True)
    return result, response


def get_markets_region_id_history(region_id: int, type_id: int) -> list["MarketsRegionIdHistoryGetItem"]:
    results = esi.client.Market.GetMarketsRegionIdHistory(
        region_id=region_id,
        type_id=type_id
    ).results()
    return results


def get_markets_structures_structure_id(structure_id: int, token: Token) -> list["MarketsStructuresStructureIdGetItem"]:
    results = esi.client.Market.GetMarketsStructuresStructureId(
        structure_id=structure_id,
        token=token
    ).results()
    return results


def get_characters_character_id_orders(character_id: "CharacterID") -> list["CharactersCharacterIdOrdersGetItem"]:
    required_scopes = ['esi-markets.read_character_orders.v1']
    token = Token.get_token(character_id, required_scopes)

    results = esi.client.Market.GetCharactersCharacterIdOrders(
        character_id=character_id,
        token=token
    ).results()
    return results


def get_characters_character_id_orders_history(character_id: "CharacterID") -> list["CharactersCharacterIdOrdersHistoryGetItem"]:
    required_scopes = ['esi-markets.read_character_orders.v1']
    token = Token.get_token(character_id, required_scopes)

    results = esi.client.Market.GetCharactersCharacterIdOrdersHistory(
        character_id=character_id,
        token=token
    ).results()
    return results


def get_characters_character_id_roles_from_token(token: Token) -> "CharactersCharacterIdRolesGet":
    # Yes this is weird, its because im pulling _specific_ scopes to find this token elsewhere
    result = esi.client.Character.GetCharactersCharacterIdRoles(
        character_id=token.character_id,
        token=token
    ).result(use_etag=False)  # TODO Implement character roles? maybe borrow corptools
    return result


def get_corporations_corporation_id_orders(corporation_id: int, token: Token) -> list["CorporationsCorporationIdOrdersGetItem"]:
    results = esi.client.Market.GetCorporationsCorporationIdOrders(
        corporation_id=corporation_id,
        token=token
    ).results()
    return results


def get_corporations_corporation_id_orders_history(corporation_id: int, token: Token) -> list["CorporationsCorporationIdOrdersHistoryGetItem"]:
    results = esi.client.Market.GetCorporationsCorporationIdOrdersHistory(
        corporation_id=corporation_id,
        token=token
    ).results()
    return results


def get_corporations_corporation_id_structures(corporation_id: int, token: Token) -> list["CorporationsCorporationIdStructuresGetItem"]:
    results = esi.client.Corporation.GetCorporationsCorporationIdStructures(
        corporation_id=corporation_id,
        token=token
    ).results()
    return results
