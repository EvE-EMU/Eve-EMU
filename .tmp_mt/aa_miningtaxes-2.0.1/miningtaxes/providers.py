from esi.openapi_clients import ESIClientProvider

from . import (
    __app_name_verbose__,
    __esi_compatibility_date__,
    __git_repo_url__,
    __version__,
)

esi = ESIClientProvider(
    compatibility_date=__esi_compatibility_date__,
    ua_appname=__app_name_verbose__,
    ua_version=__version__,
    ua_url=__git_repo_url__,
    operations=[
        "GetCorporationCorporationIdMiningObservers",
        "GetUniverseStructuresStructureId",
        "GetCharactersCharacterIdMining",
        "GetCorporationsCorporationIdWalletsDivisionJournal",
        "GetCorporationCorporationIdMiningObserversObserverId",
    ],
)
