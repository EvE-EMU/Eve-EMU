import inspect
import json
import os

from app_utils.esi_testing import EsiClientStub, EsiEndpoint

_currentdir = os.path.dirname(os.path.abspath(inspect.getfile(inspect.currentframe())))
_FILENAME_ESI_TESTDATA = "esi_testdata.json"


def load_test_data():
    with open(f"{_currentdir}/{_FILENAME_ESI_TESTDATA}", "r", encoding="utf-8") as f:
        return json.load(f)


_endpoints = [
    EsiEndpoint("Industry", "GetCharactersCharacterIdMining", "character_id"),
    EsiEndpoint(
        "Industry",
        "GetCorporationCorporationIdMiningObservers",
        "corporation_id",
    ),
    EsiEndpoint(
        "Industry",
        "GetCorporationCorporationIdMiningObserversObserverId",
        ("corporation_id", "observer_id"),
    ),
    EsiEndpoint("Universe", "GetUniverseStructuresStructureId", "structure_id"),
    EsiEndpoint(
        "Wallet",
        "GetCorporationsCorporationIdWalletsDivisionJournal",
        ("corporation_id", "division"),
    ),
]

esi_client_stub = EsiClientStub(load_test_data(), endpoints=_endpoints)
esi_client_error_stub = EsiClientStub(
    load_test_data(), endpoints=_endpoints, http_error=True
)
