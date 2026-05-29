"""Match mining observer logs and buyback trackings to scheduled moon pops."""

from __future__ import annotations

from collections import defaultdict
from datetime import timedelta

from django.contrib.auth.models import User
from django.db import transaction
from django.utils import timezone

from allianceauth.eveonline.models import EveCharacter

from .models import MoonPop, MoonPopMinerStatus


def _user_for_miner_id(miner_id: int) -> tuple[User | None, str]:
    try:
        eve = EveCharacter.objects.select_related("character_ownership__user").get(
            character_id=miner_id
        )
        ownership = getattr(eve, "character_ownership", None)
        if ownership:
            return ownership.user, eve.character_name
        return None, eve.character_name
    except EveCharacter.DoesNotExist:
        return None, str(miner_id)


def _mining_rows_for_pop(moon_pop: MoonPop) -> dict[int, dict]:
    from miningtaxes.models import AdminMiningObsLog

    start = moon_pop.pop_at.date()
    end = moon_pop.compliance_deadline().date()
    qs = (
        AdminMiningObsLog.objects.filter(
            date__gte=start,
            date__lte=end,
            eve_solar_system__name__iexact=moon_pop.system_name,
        )
        .select_related("eve_type", "eve_solar_system", "observer")
    )
    if moon_pop.moon_number is not None:
        needle = f"moon {moon_pop.moon_number}"
        qs = [r for r in qs if needle in (r.observer.name or "").lower()]
    else:
        qs = list(qs)

    by_miner: dict[int, dict] = defaultdict(
        lambda: {"quantity": 0, "ores": defaultdict(int), "character_name": ""}
    )
    for row in qs:
        entry = by_miner[row.miner_id]
        entry["quantity"] += int(row.quantity)
        entry["ores"][row.eve_type.name] += int(row.quantity)
    return by_miner


def _buyback_for_user(moon_pop: MoonPop, user: User, after) -> dict:
    from buybackprogram.models import Contract, Tracking, TrackingItem

    program_id = moon_pop.buyback_program_id
    trackings = (
        Tracking.objects.filter(
            program_id=program_id,
            issuer_user=user,
            created_at__gte=after,
        )
        .select_related("contract")
        .order_by("-created_at")
    )
    best = None
    for t in trackings:
        if best is None:
            best = t
            continue
        if t.contract_id and not best.contract_id:
            best = t
    if not best:
        return {
            "status": "no_quote",
            "tracking_id": None,
            "tracking_number": "",
            "contract_id": None,
            "has_compressed": False,
            "has_uncompressed": False,
        }

    has_compressed = False
    has_uncompressed = False
    for item in TrackingItem.objects.filter(tracking=best).select_related("eve_type"):
        name = item.eve_type.name
        if "Compressed" in name:
            has_compressed = True
        else:
            has_uncompressed = True

    if best.contract_id:
        status = MoonPopMinerStatus.STATUS_CONTRACTED
        contract_id = best.contract.contract_id
        for item in ContractItem.objects.filter(contract=best.contract).select_related(
            "eve_type"
        ):
            name = item.eve_type.name
            if "Compressed" in name:
                has_compressed = True
            else:
                has_uncompressed = True
    else:
        status = MoonPopMinerStatus.STATUS_QUOTED
        contract_id = None

    return {
        "status": status,
        "tracking_id": best.pk,
        "tracking_number": best.tracking_number,
        "contract_id": contract_id,
        "has_compressed": has_compressed,
        "has_uncompressed": has_uncompressed,
    }


@transaction.atomic
def refresh_moon_pop_compliance(moon_pop: MoonPop) -> list[MoonPopMinerStatus]:
    moon_pop.miner_statuses.all().delete()
    after = moon_pop.pop_at
    mining = _mining_rows_for_pop(moon_pop)
    results: list[MoonPopMinerStatus] = []

    users_seen: set[int] = set()
    for miner_id, data in mining.items():
        user, char_name = _user_for_miner_id(miner_id)
        if user is None:
            continue
        users_seen.add(user.pk)
        bb = _buyback_for_user(moon_pop, user, after)
        if bb["status"] == "no_quote":
            if data["quantity"] > 0:
                bb["status"] = MoonPopMinerStatus.STATUS_PENDING
            else:
                bb["status"] = MoonPopMinerStatus.STATUS_NONE
        row = MoonPopMinerStatus.objects.create(
            moon_pop=moon_pop,
            user=user,
            character_name=char_name,
            mined_quantity=data["quantity"],
            ore_summary=dict(data["ores"]),
            buyback_status=bb["status"],
            tracking_id=bb["tracking_id"],
            tracking_number=bb.get("tracking_number") or "",
            contract_id=bb.get("contract_id"),
            has_compressed=bb["has_compressed"],
            has_uncompressed=bb["has_uncompressed"],
        )
        results.append(row)

    if moon_pop.rental_kind == MoonPop.PRIVATE and moon_pop.private_owner_id:
        owner = moon_pop.private_owner
        if owner.pk not in users_seen:
            bb = _buyback_for_user(moon_pop, owner, after)
            status = bb["status"]
            if status == "no_quote":
                status = (
                    MoonPopMinerStatus.STATUS_QUOTED
                    if bb["tracking_id"]
                    else MoonPopMinerStatus.STATUS_PENDING
                )
            row = MoonPopMinerStatus.objects.create(
                moon_pop=moon_pop,
                user=owner,
                character_name=getattr(
                    getattr(owner.profile, "main_character", None),
                    "character_name",
                    owner.username,
                ),
                mined_quantity=0,
                ore_summary={},
                buyback_status=status,
                tracking_id=bb["tracking_id"],
                tracking_number=bb.get("tracking_number") or "",
                contract_id=bb.get("contract_id"),
                has_compressed=bb["has_compressed"],
                has_uncompressed=bb["has_uncompressed"],
            )
            results.append(row)

    return results
