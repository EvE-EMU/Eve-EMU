"""SRP — killmail fetch, fit grading vs doctrines, and payout calculation."""

from __future__ import annotations

import json
import logging
from datetime import UTC, datetime
from decimal import Decimal
from typing import Any, Literal

import httpx
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import settings
from app.models.tools import AuditProfile, FittingRecord, LinkedCharacter, SdeTypeIndex, SrpLoss, SrpRateRule, SsoUser
from app.services.audit_scopes import has_killmails_access, parse_granted_scopes
from app.services.audit_snapshot import load_snapshot
from app.services.audit_extras import sync_combat_log
from app.services.character_roster import roster_character_ids
from app.services.esi import bearer_token, resolve_universe_names
from app.services.zkill import fetch_killmail_zkb

logger = logging.getLogger(__name__)

_ESI = "https://esi.evetech.net/latest"
_UA = "EVE-EMU-EMUMS/1.0 (+https://emums.eve-emu.com; srp)"

FitGrade = Literal["doctrine", "meta", "shitfit"]

SLOT_FLAG_LABELS: dict[int, str] = {}
for _i in range(27, 35):
    SLOT_FLAG_LABELS[_i] = f"High {_i - 27}"
for _i in range(19, 27):
    SLOT_FLAG_LABELS[_i] = f"Med {_i - 19}"
for _i in range(11, 19):
    SLOT_FLAG_LABELS[_i] = f"Low {_i - 11}"
SLOT_FLAG_LABELS.update({92: "Rig 0", 93: "Rig 1", 94: "Rig 2"})
SLOT_FLAG_LABELS.update({125: "Sub 0", 126: "Sub 1", 127: "Sub 2", 128: "Sub 3"})

DOCTRINE_MATCH_THRESHOLD = 0.88
META_MATCH_THRESHOLD = 0.55


async def scopes_for_character(session: AsyncSession, character_id: int) -> set[str]:
    user = await session.scalar(select(SsoUser).where(SsoUser.character_id == character_id))
    if user:
        return parse_granted_scopes(user.scopes_json)
    linked = await session.scalar(
        select(LinkedCharacter).where(LinkedCharacter.character_id == character_id)
    )
    if linked:
        return parse_granted_scopes(linked.scopes_json)
    return set()


def is_fitted_flag(flag: int) -> bool:
    return flag in SLOT_FLAG_LABELS


def extract_fit_modules(killmail: dict[str, Any]) -> list[dict[str, Any]]:
    victim = killmail.get("victim") if isinstance(killmail.get("victim"), dict) else {}
    items = victim.get("items") or []
    modules: list[dict[str, Any]] = []
    for item in items:
        if not isinstance(item, dict):
            continue
        flag = int(item.get("flag") or 0)
        if not is_fitted_flag(flag):
            continue
        type_id = int(item.get("item_type_id") or 0)
        if type_id <= 0:
            continue
        qty = int(item.get("quantity_destroyed") or 0) + int(item.get("quantity_dropped") or 0)
        modules.append(
            {
                "type_id": type_id,
                "flag": flag,
                "flag_label": SLOT_FLAG_LABELS.get(flag, f"Flag {flag}"),
                "quantity": max(qty, 1),
            }
        )
    modules.sort(key=lambda m: (m["flag"], m["type_id"]))
    return modules


def doctrine_module_ids(tags_json: str) -> set[int]:
    try:
        data = json.loads(tags_json or "[]")
    except json.JSONDecodeError:
        return set()
    if isinstance(data, dict):
        raw = data.get("module_type_ids") or data.get("modules") or []
        return {int(x) for x in raw if str(x).isdigit()}
    if isinstance(data, list):
        ids: set[int] = set()
        for item in data:
            if isinstance(item, dict):
                for x in item.get("module_type_ids") or item.get("modules") or []:
                    if str(x).isdigit():
                        ids.add(int(x))
            elif str(item).isdigit():
                ids.add(int(item))
        return ids
    return set()


def grade_fit(
    ship_type_id: int,
    fitted_type_ids: set[int],
    doctrines: list[FittingRecord],
) -> dict[str, Any]:
    ship_doctrines = [d for d in doctrines if int(d.ship_type_id) == int(ship_type_id)]
    if not ship_doctrines:
        slot_count = len(fitted_type_ids)
        if slot_count >= 4:
            return {
                "fit_grade": "meta",
                "doctrine_slug": "",
                "doctrine_name": "",
                "doctrine_match_pct": 0.0,
                "matched_modules": 0,
                "expected_modules": 0,
            }
        return {
            "fit_grade": "shitfit",
            "doctrine_slug": "",
            "doctrine_name": "",
            "doctrine_match_pct": 0.0,
            "matched_modules": 0,
            "expected_modules": 0,
        }

    best_pct = 0.0
    best_slug = ""
    best_name = ""
    best_matched = 0
    best_expected = 0

    for doc in ship_doctrines:
        expected = doctrine_module_ids(doc.tags_json)
        if not expected:
            continue
        matched = len(expected & fitted_type_ids)
        pct = matched / len(expected) if expected else 0.0
        if pct > best_pct:
            best_pct = pct
            best_slug = doc.doctrine_slug
            best_name = doc.name
            best_matched = matched
            best_expected = len(expected)

    if best_pct >= DOCTRINE_MATCH_THRESHOLD:
        grade: FitGrade = "doctrine"
    elif best_pct >= META_MATCH_THRESHOLD:
        grade = "meta"
    else:
        grade = "shitfit"

    return {
        "fit_grade": grade,
        "doctrine_slug": best_slug,
        "doctrine_name": best_name,
        "doctrine_match_pct": round(best_pct * 100, 1),
        "matched_modules": best_matched,
        "expected_modules": best_expected,
    }


async def resolve_rate_rule(
    session: AsyncSession,
    *,
    ship_type_id: int,
    doctrine_slug: str = "",
) -> SrpRateRule | None:
    rows = (
        await session.scalars(
            select(SrpRateRule)
            .where(SrpRateRule.enabled.is_(True))
            .order_by(SrpRateRule.priority.desc(), SrpRateRule.id)
        )
    ).all()
    if doctrine_slug:
        for row in rows:
            if row.doctrine_slug == doctrine_slug and (
                int(row.ship_type_id) == 0 or int(row.ship_type_id) == int(ship_type_id)
            ):
                return row
    for row in rows:
        if int(row.ship_type_id) == int(ship_type_id):
            return row
    for row in rows:
        if int(row.ship_type_id) == 0 and not row.doctrine_slug:
            return row
    return None


def calculate_srp_amount(
    *,
    total_value: Decimal,
    rule: SrpRateRule | None,
    fit_grade: FitGrade,
) -> tuple[Decimal, bool, str]:
    if rule is None:
        return Decimal("0"), False, "No SRP rate configured for this ship."

    if fit_grade == "doctrine":
        mult = Decimal(str(rule.doctrine_multiplier))
    elif fit_grade == "meta":
        mult = Decimal(str(rule.meta_multiplier))
    else:
        if not rule.allow_shitfit or Decimal(str(rule.shitfit_multiplier)) <= 0:
            return Decimal("0"), False, "Shitfits are not eligible for SRP."
        mult = Decimal(str(rule.shitfit_multiplier))

    base = Decimal(str(rule.base_srp_isk))
    amount = (base * mult).quantize(Decimal("0.01"))
    if rule.max_percent is not None and total_value > 0:
        cap = (total_value * Decimal(str(rule.max_percent)) / Decimal("100")).quantize(Decimal("0.01"))
        amount = min(amount, cap)
    if amount <= 0:
        return Decimal("0"), False, "Calculated SRP amount is zero."
    return amount, True, ""


async def fetch_killmail(
    client: httpx.AsyncClient,
    killmail_id: int,
    killmail_hash: str,
) -> dict[str, Any] | None:
    resp = await client.get(
        f"{_ESI}/killmails/{killmail_id}/{killmail_hash}/",
        headers={"Accept": "application/json", "User-Agent": _UA},
    )
    if resp.status_code != 200:
        return None
    body = resp.json()
    return body if isinstance(body, dict) else None


async def enrich_fit_names(session: AsyncSession, modules: list[dict[str, Any]]) -> list[dict[str, Any]]:
    type_ids = {int(m["type_id"]) for m in modules}
    names: dict[int, str] = {}
    if type_ids:
        rows = await session.scalars(select(SdeTypeIndex).where(SdeTypeIndex.type_id.in_(type_ids)))
        names = {int(r.type_id): r.name for r in rows.all()}
    out = []
    for mod in modules:
        tid = int(mod["type_id"])
        out.append({**mod, "type_name": names.get(tid, f"Type {tid}")})
    return out


async def analyze_killmail(
    session: AsyncSession,
    *,
    killmail_id: int,
    killmail_hash: str,
    character_id: int,
) -> dict[str, Any]:
    async with httpx.AsyncClient(timeout=45.0) as client:
        km = await fetch_killmail(client, killmail_id, killmail_hash)
    if not km:
        return {"ok": False, "error": "Killmail not found on ESI."}

    victim = km.get("victim") if isinstance(km.get("victim"), dict) else {}
    victim_cid = int(victim.get("character_id") or 0)
    if victim_cid != character_id:
        return {"ok": False, "error": "This killmail is not a loss for the selected character."}

    ship_type_id = int(victim.get("ship_type_id") or 0)
    modules = extract_fit_modules(km)
    modules = await enrich_fit_names(session, modules)
    fitted_ids = {int(m["type_id"]) for m in modules}

    doctrines = (await session.scalars(select(FittingRecord))).all()
    grading = grade_fit(ship_type_id, fitted_ids, list(doctrines))

    zkb = await fetch_killmail_zkb(killmail_id)
    total_value = Decimal(str(zkb.get("total_value") or 0))

    ship_names = await resolve_universe_names([ship_type_id]) if ship_type_id else {}
    sys_id = int(km.get("solar_system_id") or 0)
    sys_names = await resolve_universe_names([sys_id]) if sys_id else {}

    rule = await resolve_rate_rule(
        session,
        ship_type_id=ship_type_id,
        doctrine_slug=str(grading.get("doctrine_slug") or ""),
    )
    fit_grade = grading["fit_grade"]
    srp_amount, eligible, block_reason = calculate_srp_amount(
        total_value=total_value,
        rule=rule,
        fit_grade=fit_grade,
    )

    existing = await session.scalar(select(SrpLoss).where(SrpLoss.killmail_id == killmail_id))

    return {
        "ok": True,
        "killmail_id": killmail_id,
        "killmail_hash": killmail_hash,
        "character_id": character_id,
        "ship_type_id": ship_type_id,
        "ship_type_name": ship_names.get(ship_type_id, f"Type {ship_type_id}"),
        "solar_system_name": sys_names.get(sys_id, ""),
        "killed_at": km.get("killmail_time"),
        "total_value_isk": str(total_value),
        "zkill_url": f"https://zkillboard.com/kill/{killmail_id}/",
        "fit_modules": modules,
        "fit_grade": fit_grade,
        "doctrine_slug": grading.get("doctrine_slug") or "",
        "doctrine_name": grading.get("doctrine_name") or "",
        "doctrine_match_pct": grading.get("doctrine_match_pct") or 0,
        "matched_modules": grading.get("matched_modules") or 0,
        "expected_modules": grading.get("expected_modules") or 0,
        "rate_rule_id": rule.id if rule else None,
        "rate_label": rule.label if rule else None,
        "srp_amount_isk": str(srp_amount),
        "eligible": eligible,
        "block_reason": block_reason,
        "already_submitted": existing is not None,
        "claim_status": existing.status if existing else None,
        "claim_id": existing.id if existing else None,
    }


async def list_eligible_losses(
    session: AsyncSession,
    *,
    viewer_character_id: int,
) -> dict[str, Any]:
    char_ids = await roster_character_ids(session, viewer_character_id)
    submitted_ids = set(
        int(x)
        for x in (
            await session.scalars(
                select(SrpLoss.killmail_id).where(SrpLoss.character_id.in_(char_ids))
            )
        ).all()
    )

    losses: dict[int, dict[str, Any]] = {}
    scope_missing: list[int] = []

    async with httpx.AsyncClient(timeout=45.0) as client:
        for cid in sorted(char_ids):
            granted = await scopes_for_character(session, cid)
            if not has_killmails_access(granted):
                scope_missing.append(cid)
                continue
            token = await bearer_token(session, character_id=cid)
            if not token:
                continue
            headers = {"Authorization": f"Bearer {token}", "User-Agent": _UA}
            events = await sync_combat_log(
                session,
                client,
                character_id=cid,
                headers=headers,
                granted=granted,
            )
            for ev in events:
                if ev.get("outcome") != "loss":
                    continue
                km_id = int(ev.get("killmail_id") or 0)
                if km_id <= 0:
                    continue
                user = await session.scalar(select(SsoUser).where(SsoUser.character_id == cid))
                linked = await session.scalar(
                    select(LinkedCharacter).where(LinkedCharacter.character_id == cid)
                )
                char_name = (
                    user.character_name
                    if user
                    else (linked.character_name if linked else f"Character {cid}")
                )
                losses[km_id] = {
                    "killmail_id": km_id,
                    "killmail_hash": str(ev.get("killmail_hash") or ""),
                    "character_id": cid,
                    "character_name": char_name,
                    "ship_type_id": ev.get("ship_type_id"),
                    "ship_type_name": ev.get("ship_type_name") or "",
                    "killed_at": ev.get("killed_at"),
                    "solar_system_name": ev.get("solar_system_name") or "",
                    "zkill_url": ev.get("zkill_url") or f"https://zkillboard.com/kill/{km_id}/",
                    "submitted": km_id in submitted_ids,
                }

    profile_rows = await session.scalars(
        select(AuditProfile).where(AuditProfile.character_id.in_(char_ids))
    )
    for profile in profile_rows.all():
        snap = load_snapshot(profile)
        for ev in snap.get("combat_log") or []:
            if not isinstance(ev, dict) or ev.get("outcome") != "loss":
                continue
            km_id = int(ev.get("killmail_id") or 0)
            if km_id <= 0 or km_id in losses:
                continue
            losses[km_id] = {
                "killmail_id": km_id,
                "killmail_hash": str(ev.get("killmail_hash") or ""),
                "character_id": int(profile.character_id),
                "character_name": profile.character_name,
                "ship_type_id": ev.get("ship_type_id"),
                "ship_type_name": ev.get("ship_type_name") or "",
                "killed_at": ev.get("killed_at"),
                "solar_system_name": ev.get("solar_system_name") or "",
                "zkill_url": ev.get("zkill_url") or f"https://zkillboard.com/kill/{km_id}/",
                "submitted": km_id in submitted_ids,
            }

    rows = sorted(losses.values(), key=lambda r: str(r.get("killed_at") or ""), reverse=True)
    return {
        "losses": rows[:40],
        "scope_note": (
            "Grant esi-killmails.read_killmails.v1 on linked characters to pull recent losses from ESI."
            if scope_missing
            else None
        ),
    }


async def submit_srp_claim(
    session: AsyncSession,
    *,
    viewer_character_id: int,
    killmail_id: int,
    killmail_hash: str,
    character_id: int,
    notes: str = "",
) -> dict[str, Any]:
    allowed = await roster_character_ids(session, viewer_character_id)
    if character_id not in allowed:
        return {"ok": False, "error": "Character not in your linked roster."}

    existing = await session.scalar(select(SrpLoss).where(SrpLoss.killmail_id == killmail_id))
    if existing:
        return {"ok": False, "error": "SRP already submitted for this killmail.", "claim_id": existing.id}

    preview = await analyze_killmail(
        session,
        killmail_id=killmail_id,
        killmail_hash=killmail_hash,
        character_id=character_id,
    )
    if not preview.get("ok"):
        return preview
    if not preview.get("eligible"):
        return {"ok": False, "error": preview.get("block_reason") or "Not eligible for SRP."}

    user = await session.scalar(select(SsoUser).where(SsoUser.character_id == character_id))
    linked = await session.scalar(
        select(LinkedCharacter).where(LinkedCharacter.character_id == character_id)
    )
    char_name = (
        user.character_name if user else (linked.character_name if linked else f"Character {character_id}")
    )

    killed_at = None
    raw_time = preview.get("killed_at")
    if raw_time:
        try:
            killed_at = datetime.fromisoformat(str(raw_time).replace("Z", "+00:00"))
        except ValueError:
            killed_at = None

    row = SrpLoss(
        killmail_id=killmail_id,
        killmail_hash=killmail_hash,
        character_id=character_id,
        character_name=char_name,
        ship_type_id=int(preview.get("ship_type_id") or 0),
        ship_type_name=str(preview.get("ship_type_name") or ""),
        total_value_isk=Decimal(str(preview.get("total_value_isk") or 0)),
        srp_amount_isk=Decimal(str(preview.get("srp_amount_isk") or 0)),
        fit_json=json.dumps(preview.get("fit_modules") or []),
        fit_grade=str(preview.get("fit_grade") or "shitfit"),
        doctrine_slug=str(preview.get("doctrine_slug") or ""),
        doctrine_match_pct=float(preview.get("doctrine_match_pct") or 0),
        submitted_notes=notes.strip()[:2000],
        status="pending",
        zkill_url=str(preview.get("zkill_url") or ""),
        solar_system_name=str(preview.get("solar_system_name") or ""),
        killed_at=killed_at,
        submitted_at=datetime.now(UTC),
    )
    session.add(row)
    await session.commit()
    await session.refresh(row)
    return {"ok": True, "claim_id": row.id, "status": row.status, "srp_amount_isk": str(row.srp_amount_isk)}


async def list_rate_rules(session: AsyncSession, *, enabled_only: bool = False) -> list[SrpRateRule]:
    q = select(SrpRateRule).order_by(SrpRateRule.priority.desc(), SrpRateRule.label)
    if enabled_only:
        q = q.where(SrpRateRule.enabled.is_(True))
    return list((await session.scalars(q)).all())
