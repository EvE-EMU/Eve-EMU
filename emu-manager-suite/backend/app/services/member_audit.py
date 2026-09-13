"""Member audit ESI sync and security flag engine."""

from __future__ import annotations

import logging
from datetime import UTC, datetime
from decimal import Decimal

import httpx
from sqlalchemy import delete, insert, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.member_audit import AuditSecurityFlag, CharacterAsset, CharacterWalletJournal
from app.models.tools import AuditProfile, HrBlacklistEntry, LinkedCharacter, SdeTypeIndex, SsoUser
from app.services.audit_scopes import (
    has_assets_access,
    has_corp_assets_access,
    has_pi_access,
    has_wallet_access,
    missing_scopes,
    parse_granted_scopes,
)
from app.services.audit_snapshot import load_snapshot, save_snapshot, sync_audit_snapshot
from app.services.asset_labels import load_type_names, resolve_type_name
from app.services.esi import bearer_token, esi_get_paged_list
from app.services.isk_format import fmt_isk_full
from app.services.universe_locations import ensure_universe_locations

logger = logging.getLogger(__name__)
_ESI = "https://esi.evetech.net/latest"
_UA = "EVE-EMU-EMUMS/1.0 (+https://emums.eve-emu.com; audit)"


async def sync_character_audit(session: AsyncSession, character_id: int) -> dict[str, int | list[str] | dict[str, str]]:
    user = await session.scalar(select(SsoUser).where(SsoUser.character_id == character_id))
    granted = parse_granted_scopes(user.scopes_json if user else "")
    missing = missing_scopes(granted)
    scope_errors: dict[str, str] = {}

    token = await bearer_token(session, character_id=character_id)
    if not token:
        return {
            "wallet_rows": 0,
            "assets": 0,
            "flags": 0,
            "missing_scopes": missing,
            "scope_errors": {"token": "No valid SSO token — log in again."},
        }

    headers = {"Authorization": f"Bearer {token}", "User-Agent": _UA}
    wallet_rows = 0
    assets = 0
    flags = 0
    wallet_balance = Decimal("0")
    skill_points = 0

    profile = await session.scalar(
        select(AuditProfile).where(AuditProfile.character_id == character_id)
    )
    if profile is None:
        profile = AuditProfile(
            character_id=character_id,
            character_name=user.character_name if user else f"Character {character_id}",
            corporation_name=user.corporation_name if user else "",
        )
        session.add(profile)
    elif user:
        profile.character_name = user.character_name
        profile.corporation_name = user.corporation_name or profile.corporation_name

    prev_snapshot = load_snapshot(profile)
    prev_wallet = Decimal(str(prev_snapshot.get("wallet_balance_isk") or profile.wallet_balance_isk or 0))

    async with httpx.AsyncClient(timeout=60.0) as client:
        # Snapshot (skills, queue, location, clones, contracts) before heavy asset pagination.
        await sync_audit_snapshot(
            session,
            client=client,
            character_id=character_id,
            headers=headers,
            granted=granted,
            user=user,
            profile=profile,
            scope_errors=scope_errors,
        )
        skill_points = int(profile.skill_points or 0)

        if has_wallet_access(granted):
            try:
                bal_resp = await client.get(
                    f"{_ESI}/characters/{character_id}/wallet/",
                    headers=headers,
                )
                if bal_resp.status_code == 200:
                    wallet_balance = Decimal(str(bal_resp.json() or 0))
                elif bal_resp.status_code in (401, 403):
                    scope_errors["wallet"] = bal_resp.text[:200]
            except Exception:
                logger.exception("audit wallet balance failed for %s", character_id)

            try:
                wresp = await client.get(
                    f"{_ESI}/characters/{character_id}/wallet/journal/",
                    headers=headers,
                    params={"page": 1},
                )
                if wresp.status_code == 200:
                    page_rows = wresp.json()
                    incoming_ids = [
                        int(row.get("id") or 0) for row in page_rows if int(row.get("id") or 0) > 0
                    ]
                    existing_ids: set[int] = set()
                    if incoming_ids:
                        existing_ids = set(
                            int(jid)
                            for jid in (
                                await session.scalars(
                                    select(CharacterWalletJournal.journal_id).where(
                                        CharacterWalletJournal.journal_id.in_(incoming_ids)
                                    )
                                )
                            ).all()
                        )
                    for row in page_rows:
                        jid = int(row.get("id") or 0)
                        if not jid or jid in existing_ids:
                            continue
                        session.add(
                            CharacterWalletJournal(
                                character_id=character_id,
                                journal_id=jid,
                                ref_type=str(row.get("ref_type") or ""),
                                amount=Decimal(str(row.get("amount") or 0)),
                                balance=Decimal(str(row.get("balance") or 0)),
                                first_party_id=row.get("first_party_id"),
                                second_party_id=row.get("second_party_id"),
                                reason=str(row.get("reason") or "")[:512],
                                recorded_at=datetime.fromisoformat(
                                    str(row.get("date") or "").replace("Z", "+00:00")
                                ),
                            )
                        )
                        wallet_rows += 1
                elif wresp.status_code in (401, 403):
                    scope_errors["wallet_journal"] = wresp.text[:200]
            except Exception:
                logger.exception("audit wallet sync failed for %s", character_id)
        else:
            scope_errors["wallet"] = "Missing scope: esi-wallet.read_character_wallet.v1"

        if has_assets_access(granted):
            try:
                asset_rows = await esi_get_paged_list(
                    f"/characters/{character_id}/assets/",
                    auth=True,
                    session=session,
                    character_id=character_id,
                    max_pages=50,
                )
                corp_id = int(user.corporation_id or 0) if user else 0
                corp_hangar_rows: list[dict] = []
                if corp_id > 0 and has_corp_assets_access(granted):
                    try:
                        corp_asset_rows = await esi_get_paged_list(
                            f"/corporations/{corp_id}/assets/",
                            auth=True,
                            session=session,
                            character_id=character_id,
                            max_pages=100,
                        )
                        corp_hangar_rows = [
                            row
                            for row in corp_asset_rows
                            if isinstance(row, dict)
                            and str(row.get("location_flag") or "").startswith("CorpSAG")
                        ]
                    except Exception:
                        logger.exception("audit corp asset sync failed for %s", character_id)
                elif corp_id > 0:
                    scope_errors["corp_assets"] = (
                        "Missing scope: esi-assets.read_corporation_assets.v1 — "
                        "re-link SSO for corp hangar stock."
                    )

                all_asset_rows = [
                    row for row in asset_rows if isinstance(row, dict)
                ] + corp_hangar_rows

                await session.execute(
                    delete(CharacterAsset).where(CharacterAsset.character_id == character_id)
                )
                type_ids = {
                    int(row.get("type_id") or 0)
                    for row in all_asset_rows
                    if int(row.get("type_id") or 0) > 0
                }
                type_names = await load_type_names(session, type_ids)
                item_names: dict[int, str] = {}
                try:
                    names_resp = await client.get(
                        f"{_ESI}/characters/{character_id}/assets/names/",
                        headers=headers,
                    )
                    if names_resp.status_code == 200:
                        for row in names_resp.json() or []:
                            if isinstance(row, dict):
                                iid = int(row.get("item_id") or 0)
                                nm = str(row.get("name") or "").strip()
                                if iid > 0 and nm:
                                    item_names[iid] = nm[:256]
                except Exception:
                    logger.exception("audit asset names failed for %s", character_id)

                if corp_id > 0 and corp_hangar_rows:
                    try:
                        corp_item_ids = [
                            int(row.get("item_id") or 0)
                            for row in corp_hangar_rows
                            if int(row.get("item_id") or 0) > 0
                        ]
                        if corp_item_ids:
                            names_resp = await client.post(
                                f"{_ESI}/corporations/{corp_id}/assets/names/",
                                headers=headers,
                                json=corp_item_ids[:1000],
                            )
                            if names_resp.status_code == 200:
                                for row in names_resp.json() or []:
                                    if isinstance(row, dict):
                                        iid = int(row.get("item_id") or 0)
                                        nm = str(row.get("name") or "").strip()
                                        if iid > 0 and nm:
                                            item_names[iid] = nm[:256]
                    except Exception:
                        logger.exception("audit corp asset names failed for %s", character_id)

                location_ids = {
                    int(row.get("location_id") or 0)
                    for row in all_asset_rows
                    if int(row.get("location_id") or 0) > 0
                }
                await ensure_universe_locations(
                    session, list(location_ids), character_id=character_id
                )

                asset_mappings: list[dict] = []
                for row in all_asset_rows:
                    tid = int(row.get("type_id") or 0)
                    iid = int(row.get("item_id") or 0)
                    flag = str(row.get("location_flag") or "")
                    asset_mappings.append(
                        {
                            "character_id": character_id,
                            "item_id": iid,
                            "type_id": tid,
                            "type_name": resolve_type_name(
                                tid, type_names.get(tid, ""), flag=flag
                            ),
                            "custom_name": item_names.get(iid, ""),
                            "quantity": int(row.get("quantity") or 0),
                            "location_id": int(row.get("location_id") or 0),
                            "flag": flag,
                        }
                    )
                if asset_mappings:
                    await session.execute(insert(CharacterAsset), asset_mappings)
                assets = len(asset_mappings)
            except Exception:
                logger.exception("audit asset sync failed for %s", character_id)
        else:
            scope_errors["assets"] = "Missing scope: esi-assets.read_assets.v1"

    profile.wallet_balance_isk = wallet_balance
    if skill_points:
        profile.skill_points = skill_points
    profile.last_sync_at = datetime.now(UTC)
    snapshot = load_snapshot(profile)
    if scope_errors:
        snapshot["scope_errors"] = dict(scope_errors)
    save_snapshot(profile, snapshot)

    from app.services.interaction_sync import sync_character_interactions
    from app.services.hr_alert_engine import evaluate_hr_audit_rules
    from app.services.webhook_notification_engine import evaluate_webhook_notifications

    char_name = profile.character_name or (user.character_name if user else f"Character {character_id}")
    prev_snapshot["wallet_balance_isk"] = str(prev_wallet)
    snapshot["wallet_balance_isk"] = str(wallet_balance)

    await sync_character_interactions(session, character_id)
    flags = await run_security_checks(session, character_id, prev_wallet=prev_wallet)
    flags += await evaluate_hr_audit_rules(session, character_id, prev_wallet=prev_wallet)
    await evaluate_webhook_notifications(
        session,
        character_id,
        character_name=char_name,
        prev_snapshot=prev_snapshot,
        new_snapshot=snapshot,
        scope_errors=scope_errors,
    )

    from app.services.industry_sync import sync_character_industry
    from app.services.market_sync import sync_character_market_orders
    from app.services.structure_sync import sync_character_structures

    industry = await sync_character_industry(
        session, character_id, granted=granted, scope_errors=scope_errors
    )
    market_orders = await sync_character_market_orders(
        session, character_id, granted=granted, scope_errors=scope_errors
    )
    structures = await sync_character_structures(
        session, character_id, granted=granted, scope_errors=scope_errors
    )

    return {
        "wallet_rows": wallet_rows,
        "assets": assets,
        "flags": flags,
        "missing_scopes": missing,
        "scope_errors": scope_errors,
        "fittings": industry.get("fittings", 0),
        "blueprints": industry.get("blueprints", 0),
        "industry_jobs": industry.get("jobs", 0),
        "mining_rows": industry.get("mining", 0),
        "market_orders": market_orders,
        "structures": structures,
    }


async def run_security_checks(
    session: AsyncSession, character_id: int, *, prev_wallet: Decimal | None = None
) -> int:
    created = 0
    profile = await session.scalar(
        select(AuditProfile).where(AuditProfile.character_id == character_id)
    )
    char_name = profile.character_name if profile else f"Character {character_id}"

    blacklist = {
        int(r.character_id)
        for r in (
            await session.scalars(
                select(HrBlacklistEntry).where(
                    HrBlacklistEntry.active.is_(True),
                    HrBlacklistEntry.character_id.isnot(None),
                )
            )
        ).all()
        if r.character_id is not None
    }

    open_flag_keys = set(
        await session.scalars(
            select(AuditSecurityFlag.flag_key).where(
                AuditSecurityFlag.character_id == character_id,
                AuditSecurityFlag.resolved.is_(False),
            )
        )
    )

    journals = await session.scalars(
        select(CharacterWalletJournal)
        .where(CharacterWalletJournal.character_id == character_id)
        .order_by(CharacterWalletJournal.recorded_at.desc())
        .limit(50)
    )
    for entry in journals.all():
        party = entry.second_party_id or entry.first_party_id
        if party and int(party) in blacklist:
            key = f"blacklist_contact:{party}"
            if key not in open_flag_keys:
                session.add(
                    AuditSecurityFlag(
                        character_id=character_id,
                        character_name=char_name,
                        flag_key=key,
                        severity="critical",
                        detail=f"Wallet journal references blacklisted entity {party}",
                    )
                )
                open_flag_keys.add(key)
                created += 1

    if profile and prev_wallet is not None and prev_wallet > 0:
        drop = prev_wallet - profile.wallet_balance_isk
        if drop > prev_wallet * Decimal("0.5") and "wallet_drop" not in open_flag_keys:
            session.add(
                AuditSecurityFlag(
                    character_id=character_id,
                    character_name=char_name,
                    flag_key="wallet_drop",
                    severity="warn",
                    detail=f"Wallet dropped {fmt_isk_full(drop)} since last snapshot",
                )
            )
            created += 1

    return created


async def collect_audit_character_ids(session: AsyncSession) -> list[int]:
    """All pilots that should participate in coalition audit sync."""
    linked = [int(cid) for cid in (await session.scalars(select(LinkedCharacter.character_id))).all()]
    mains = [int(cid) for cid in (await session.scalars(select(SsoUser.character_id))).all()]
    return sorted(set(linked + mains))


async def enqueue_stale_audit_syncs(session: AsyncSession) -> dict[str, int]:
    """Queue Celery audit tasks for characters stale since last sync — avoids one giant loop."""
    from datetime import timedelta

    from app.config import settings

    character_ids = await collect_audit_character_ids(session)
    if not character_ids:
        return {"queued": 0, "skipped_fresh": 0, "total_characters": 0}

    cutoff = datetime.now(UTC) - timedelta(minutes=max(5, settings.audit_sync_stale_minutes))
    profile_rows = (
        await session.execute(
            select(AuditProfile.character_id, AuditProfile.last_sync_at).where(
                AuditProfile.character_id.in_(character_ids)
            )
        )
    ).all()
    last_sync = {int(cid): ts for cid, ts in profile_rows}

    stale: list[int] = []
    fresh = 0
    users_by_id: dict[int, SsoUser] = {}
    if character_ids:
        for user in (
            await session.scalars(select(SsoUser).where(SsoUser.character_id.in_(character_ids)))
        ).all():
            users_by_id[int(user.character_id)] = user

    for cid in character_ids:
        ts = last_sync.get(cid)
        user = users_by_id.get(cid)
        granted = parse_granted_scopes(user.scopes_json if user else "")
        profile = None
        if has_pi_access(granted):
            profile = await session.scalar(
                select(AuditProfile).where(AuditProfile.character_id == cid)
            )
            snap = load_snapshot(profile)
            pi = snap.get("pi") if isinstance(snap.get("pi"), dict) else {}
            if not pi.get("synced_at"):
                stale.append(cid)
                continue
        if ts is None or ts < cutoff:
            stale.append(cid)
        else:
            fresh += 1

    from app.tasks.member_audit import sync_character_audit_task

    batch = max(1, settings.audit_sync_batch_size)
    queued = 0
    for cid in stale[:batch]:
        sync_character_audit_task.apply_async(args=[int(cid)], queue="audit")
        queued += 1

    return {
        "queued": queued,
        "skipped_fresh": fresh,
        "stale_remaining": max(0, len(stale) - queued),
        "total_characters": len(character_ids),
    }


async def sync_all_registered_characters(session: AsyncSession) -> dict[str, int]:
    """Beat entrypoint — fan out to per-character Celery tasks instead of blocking."""
    result = await enqueue_stale_audit_syncs(session)
    return {
        "characters": int(result.get("total_characters") or 0),
        "wallet_rows": 0,
        "assets": 0,
        "flags": 0,
        "queued": int(result.get("queued") or 0),
        "skipped_fresh": int(result.get("skipped_fresh") or 0),
        "stale_remaining": int(result.get("stale_remaining") or 0),
    }
