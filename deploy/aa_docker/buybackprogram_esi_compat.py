"""aa-buybackprogram on django-esi 9: Token object + dict-shaped ESI rows."""

from __future__ import annotations

import json
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


def _patch_update_contracts_esi(owner_cls, fetch_token_for_owner) -> None:
    """Do not require corp contract scope to run sync (Charlink often omits it)."""
    from allianceauth.services.hooks import get_extension_logger
    from buybackprogram.app_settings import (
        BUYBACKPROGRAM_TRACK_PREFILL_CONTRACTS,
        BUYBACKPROGRAM_TRACKING_PREFILL,
    )
    from buybackprogram.models import Tracking
    from esi.errors import TokenError

    logger = get_extension_logger("buybackprogram.models")

    @fetch_token_for_owner(
        [
            "esi-contracts.read_character_contracts.v1",
            "esi-universe.read_structures.v1",
        ]
    )
    def update_contracts_esi(owner, token):
        logger.debug("Fetching contracts for %s" % owner.character)

        contracts = owner._fetch_contracts()
        logger.debug("Got %s character contracts" % len(contracts))

        logger.debug("Fetching corporation contracts for %s" % owner.corporation)
        try:
            corporation_contracts = owner._fetch_corporation_contracts()
        except TokenError:
            logger.warning(
                "%s: Skipping corporation contracts (no corp contract scope)",
                owner,
            )
            corporation_contracts = []

        logger.debug("Got %s corporation contracts" % len(corporation_contracts))

        all_contracts = contracts + corporation_contracts
        tracked_contrats = list()

        logger.debug("Total contracts received: %s" % len(all_contracts))

        tracking_numbers = Tracking.objects.all()
        logger.debug("Got %s tracking numbers from database" % len(tracking_numbers))

        for tracking in tracking_numbers:
            if tracking.program:
                for contract in all_contracts:
                    if tracking.tracking_number in contract["title"]:
                        owner._process_contract(contract, tracking, token)
                        tracked_contrats.append(contract)
                        break

        if BUYBACKPROGRAM_TRACK_PREFILL_CONTRACTS:
            logger.debug("Starting untracked contracts check")
            untracked_contracts = [
                x for x in all_contracts if x not in tracked_contrats
            ]
            logger.debug(
                "Found %s untracked contracts out of %s"
                % (len(untracked_contracts), len(all_contracts))
            )
            for contract in untracked_contracts:
                if BUYBACKPROGRAM_TRACKING_PREFILL in contract["title"]:
                    try:
                        tracking = Tracking.objects.get(
                            tracking_number__contains=contract["title"]
                        )
                        logger.debug(
                            "Contract %s matched tracking %s via prefill, processing"
                            % (contract["contract_id"], tracking.tracking_number)
                        )
                        owner._process_contract(contract, tracking, token)
                        tracked_contrats.append(contract)
                    except Tracking.DoesNotExist:
                        logger.debug(
                            "Contract %s is not tracked, starting updates"
                            % contract["contract_id"]
                        )
                        owner._process_contract_without_tracking(contract, token)
        else:
            logger.debug(
                "Track prefill contracts is set to %s, passing prefill contract checks"
                % BUYBACKPROGRAM_TRACK_PREFILL_CONTRACTS
            )

    owner_cls.update_contracts_esi = update_contracts_esi


def _normalize_discord_webhook_url(webhook: str) -> str | None:
    webhook = (webhook or "").strip()
    if webhook.startswith("http"):
        return webhook
    try:
        data = json.loads(webhook)
    except (json.JSONDecodeError, TypeError):
        return None
    webhook_id = data.get("id")
    token = data.get("token")
    if webhook_id and token:
        return f"https://discord.com/api/webhooks/{webhook_id}/{token}"
    return None


def _patch_buyback_discord_notifications() -> None:
    try:
        import buybackprogram.notification as notification
    except ImportError:
        return

    if getattr(notification, "_eve_emu_discord_patch", False):
        return

    from allianceauth.services.hooks import get_extension_logger

    logger = get_extension_logger("buybackprogram.notification")
    original = notification.send_message_to_discord_channel

    def send_message_to_discord_channel(webhook, message: dict, embed: bool = False):
        url = _normalize_discord_webhook_url(webhook)
        if not url:
            logger.error(
                "Invalid buyback Discord webhook (%r); skipping channel notification",
                (webhook or "")[:120],
            )
            return
        try:
            original(url, message, embed)
        except Exception as exc:
            logger.error("Buyback Discord webhook failed: %s", exc)

    notification.send_message_to_discord_channel = send_message_to_discord_channel
    try:
        import buybackprogram.models as buyback_models

        buyback_models.send_message_to_discord_channel = send_message_to_discord_channel
    except ImportError:
        pass
    notification._eve_emu_discord_patch = True


def patch_buybackprogram_esi() -> None:
    try:
        from buybackprogram.decorators import fetch_token_for_owner
        from buybackprogram.models import Owner
        from buybackprogram.providers import esi
    except ImportError:
        return

    if not getattr(Owner, "_eve_emu_update_contracts_scope_patch", False):
        _patch_update_contracts_esi(Owner, fetch_token_for_owner)
        Owner._eve_emu_update_contracts_scope_patch = True

    _patch_buyback_discord_notifications()

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
