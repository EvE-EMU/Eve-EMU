"""CorpTools: ESI contracts may omit issuer_id; ORM also requires integer issuer_* columns."""

from __future__ import annotations

import logging
import types

logger = logging.getLogger(__name__)


def _party_ids(esi_model, *, fallback_corp_id: int) -> tuple[int, int, int, int]:
    issuer_corp_id = esi_model.issuer_corporation_id or fallback_corp_id
    issuer_id = esi_model.issuer_id or issuer_corp_id
    assignee_id = esi_model.assignee_id if esi_model.assignee_id is not None else 0
    acceptor_id = (
        esi_model.acceptor_id
        if esi_model.acceptor_id is not None
        else (assignee_id or issuer_id)
    )
    return issuer_id, issuer_corp_id, acceptor_id, assignee_id


def patch_corptools_contract_from_esi() -> None:
    from django.apps import apps

    if not apps.is_installed("corptools"):
        return

    from corptools.models import Contract, CorporateContract, EveName

    @classmethod
    def contract_from_esi(cls, character, esi_model):
        corp_id = character.character.corporation_id
        issuer_id, issuer_corp_id, acceptor_id, assignee_id = _party_ids(
            esi_model, fallback_corp_id=corp_id
        )
        return cls(
            id=cls.build_pk(character.id, esi_model.contract_id),
            character=character,
            assignee_id=assignee_id,
            assignee_name_id=assignee_id,
            acceptor_id=acceptor_id,
            acceptor_name_id=acceptor_id,
            contract_id=esi_model.contract_id,
            availability=esi_model.availability,
            buyout=esi_model.buyout,
            collateral=esi_model.collateral,
            date_accepted=esi_model.date_accepted,
            date_completed=esi_model.date_completed,
            date_expired=esi_model.date_expired,
            date_issued=esi_model.date_issued,
            days_to_complete=esi_model.days_to_complete,
            end_location_id=esi_model.end_location_id,
            for_corporation=esi_model.for_corporation,
            issuer_corporation_id=issuer_corp_id,
            issuer_corporation_name_id=issuer_corp_id,
            issuer_id=issuer_id,
            issuer_name_id=issuer_id,
            price=esi_model.price,
            reward=esi_model.reward,
            start_location_id=esi_model.start_location_id,
            status=esi_model.status,
            title=esi_model.title,
            contract_type=esi_model.type,
            volume=esi_model.volume,
        )

    @staticmethod
    def corporate_contract_from_esi(corporation, esi_model):
        corp_id = corporation.corporation.corporation_id
        issuer_id, issuer_corp_id, acceptor_id, assignee_id = _party_ids(
            esi_model, fallback_corp_id=corp_id
        )
        return CorporateContract(
            id=CorporateContract.build_pk(corporation.id, esi_model.contract_id),
            corporation=corporation,
            assignee_id=assignee_id,
            assignee_name_id=assignee_id,
            acceptor_id=acceptor_id,
            acceptor_name_id=acceptor_id,
            contract_id=esi_model.contract_id,
            availability=esi_model.availability,
            buyout=esi_model.buyout,
            collateral=esi_model.collateral,
            date_accepted=esi_model.date_accepted,
            date_completed=esi_model.date_completed,
            date_expired=esi_model.date_expired,
            date_issued=esi_model.date_issued,
            days_to_complete=esi_model.days_to_complete,
            end_location_id=esi_model.end_location_id,
            for_corporation=esi_model.for_corporation,
            issuer_corporation_id=issuer_corp_id,
            issuer_corporation_name_id=issuer_corp_id,
            issuer_id=issuer_id,
            issuer_name_id=issuer_id,
            price=esi_model.price,
            reward=esi_model.reward,
            start_location_id=esi_model.start_location_id,
            status=esi_model.status,
            title=esi_model.title,
            contract_type=esi_model.type,
            volume=esi_model.volume,
        )

    Contract.from_esi_model = contract_from_esi  # type: ignore[method-assign]
    CorporateContract.from_esi_model = corporate_contract_from_esi  # type: ignore[method-assign]

    _orig_bulk = EveName.objects.create_bulk_from_esi

    def create_bulk_from_esi(self, eve_ids):
        filtered = [i for i in eve_ids if i is not None]
        return _orig_bulk(filtered)

    EveName.objects.create_bulk_from_esi = types.MethodType(
        create_bulk_from_esi, EveName.objects
    )

    logger.debug("corptools_contracts_patch: patched Contract.from_esi_model")
