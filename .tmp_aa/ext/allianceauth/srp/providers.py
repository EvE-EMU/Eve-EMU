from typing import TYPE_CHECKING

from esi.openapi_clients import ESIClientProvider

if TYPE_CHECKING:
    from esi.stubs import (
        KillmailsKillmailIdKillmailHashGet, UniverseTypesTypeIdGet,
    )

from allianceauth import __title__, __url__, __version__

from . import __esi_compatibility_date__

esi = ESIClientProvider(
    ua_appname=__title__,
    ua_version=__version__,
    ua_url=__url__,
    compatibility_date=__esi_compatibility_date__,
    operations=[
        "GetKillmailsKillmailIdKillmailHash",
        "GetUniverseTypesTypeId",
    ]
)


def get_killmails_killmail_id_killmail_hash(killmail_id: int, killmail_hash: str) -> "KillmailsKillmailIdKillmailHashGet":
    return esi.client.Killmails.GetKillmailsKillmailIdKillmailHash(killmail_hash=killmail_hash, killmail_id=killmail_id).result()


def get_universe_types_type_id(type_id: int) -> "UniverseTypesTypeIdGet":
    return esi.client.Universe.GetUniverseTypesTypeId(type_id=type_id).result()
