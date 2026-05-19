from typing import TYPE_CHECKING

from esi.models import Token
from esi.openapi_clients import ESIClientProvider

from .. import __title__, __url__, __version__
from . import __esi_compatibility_date__

if TYPE_CHECKING:
    from esi.stubs import (
        CharactersDetail, CorporationsCorporationIdMembersGet,
        PostUniverseNamesOperation, PostUniverseNamesOperationBody,
    )

esi = ESIClientProvider(
    ua_appname=__title__,
    ua_version=__version__,
    ua_url=__url__,
    compatibility_date=__esi_compatibility_date__,
    operations=[
        "GetCharactersCharacterId",
        "GetCorporationsCorporationIdMembers",
        "PostUniverseNames",
    ])


def get_characters_character_id(character_id: int) -> "CharactersDetail":
    return esi.client.Character.GetCharactersCharacterId(character_id=character_id).result()


def get_corporations_corporation_id_members(corporation_id: int, token: Token) -> "CorporationsCorporationIdMembersGet":
    return esi.client.Corporation.GetCorporationsCorporationIdMembers(corporation_id=corporation_id, token=token).result()


def post_universe_names(ids: "PostUniverseNamesOperationBody") -> "PostUniverseNamesOperation":
    # store_cache = false, we are unlikely to make the same request again
    return esi.client.Universe.PostUniverseNames(body=ids).result(store_cache=False)
