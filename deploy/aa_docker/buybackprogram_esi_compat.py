"""aa-buybackprogram on django-esi 9: Token object + dict-shaped ESI rows."""

from __future__ import annotations

from typing import Any

from esi.exceptions import HTTPNotModified


def _esi_results(operation) -> list:
    """Contract polling must not treat an all-304 etag run as zero contracts."""
    try:
        return operation.results(use_etag=False)
    except HTTPNotModified:
        return []


def esi_row_to_dict(row: Any) -> dict[str, Any]:
    if isinstance(row, dict):
        return dict(row)
    if hasattr(row, "model_dump"):
        return row.model_dump()
    if hasattr(row, "__dict__"):
        return {k: v for k, v in row.__dict__.items() if not k.startswith("_")}
    raise TypeError(f"Cannot convert ESI row to dict: {type(row)!r}")


def patch_buybackprogram_esi() -> None:
    try:
        from buybackprogram.decorators import fetch_token_for_owner
        from buybackprogram.models import Owner
        from buybackprogram.providers import esi
    except ImportError:
        return

    if getattr(Owner, "_eve_emu_esi9_patch", False):
        return

    @fetch_token_for_owner(["esi-contracts.read_character_contracts.v1"])
    def _fetch_contracts(owner, token) -> list:
        character_id = owner.character.character.character_id
        esi_contracts = _esi_results(
            esi.client.Contracts.get_characters_character_id_contracts(
                character_id=character_id,
                token=token,
            )
        )
        contracts = []
        for esi_contract in esi_contracts:
            contract = esi_row_to_dict(esi_contract)
            contract["is_corporation"] = False
            contracts.append(contract)
        return contracts

    @fetch_token_for_owner(["esi-contracts.read_corporation_contracts.v1"])
    def _fetch_corporation_contracts(owner, token) -> list:
        corporation_id = owner.character.character.corporation_id
        esi_contracts = _esi_results(
            esi.client.Contracts.get_corporations_corporation_id_contracts(
                corporation_id=corporation_id,
                token=token,
            )
        )
        contracts = []
        for esi_contract in esi_contracts:
            contract = esi_row_to_dict(esi_contract)
            contract["is_corporation"] = True
            contracts.append(contract)
        return contracts

    @fetch_token_for_owner(["esi-universe.read_structures.v1"])
    def _get_location_name(owner, token, structid) -> str:
        from eveuniverse.models import EveEntity

        if structid <= 100000000:
            return EveEntity.objects.resolve_name(structid)

        operation = esi.client.Universe.get_universe_structures_structure_id(
            structure_id=structid,
            token=token,
        )
        try:
            label = operation.result(use_etag=False)
            label = esi_row_to_dict(label)
        except (OSError, Exception):
            return "Unknown"
        return label.get("name", "Unknown")

    Owner._fetch_contracts = _fetch_contracts
    Owner._fetch_corporation_contracts = _fetch_corporation_contracts
    Owner._get_location_name = _get_location_name
    Owner._eve_emu_esi9_patch = True
