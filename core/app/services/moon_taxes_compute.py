"""Moon mining tax helper: mining ledger vs contracts (and optional assets) with ISK hints."""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import UTC, datetime, timedelta
from typing import Any
from uuid import UUID

import httpx
from sqlalchemy import select

from app.config import settings
from app.db.models import CoreUser, EveLinkedCharacter
from app.db.session import session_scope
from app.db.token_store import get_eve_refresh_token_plain, upsert_eve_refresh_token
from app.services.esi_http import esi_get_json
from app.services.esi_paged import esi_get_paged_json_list
from app.services.eve_sso_http import refresh_access_token


def _parse_esi_dt(raw: str | None) -> datetime | None:
    if not raw:
        return None
    s = raw.replace("Z", "+00:00")
    try:
        return datetime.fromisoformat(s)
    except ValueError:
        return None


async def _markets_adjusted_prices() -> dict[int, float]:
    url = "https://esi.evetech.net/latest/markets/prices/"
    headers = {"Accept": "application/json", "User-Agent": "EVE-EMU-Core/1.0 (+moon-taxes)"}
    async with httpx.AsyncClient(timeout=60.0) as client:
        resp = await client.get(url, headers=headers)
        resp.raise_for_status()
        data = resp.json()
    out: dict[int, float] = {}
    if not isinstance(data, list):
        return out
    for row in data:
        if not isinstance(row, dict):
            continue
        try:
            tid = int(row["type_id"])
        except (KeyError, TypeError, ValueError):
            continue
        ap = row.get("adjusted_price")
        if ap is None:
            continue
        try:
            out[tid] = float(ap)
        except (TypeError, ValueError):
            continue
    return out


async def _universe_type_name(type_id: int) -> str:
    data = await esi_get_json(f"/universe/types/{type_id}/")
    if not data:
        return f"type {type_id}"
    name = data.get("name")
    return str(name).strip() if name else f"type {type_id}"


async def _access_token_for_character(*, character_id: int, owner_user_id: UUID) -> str | None:
    rt = await get_eve_refresh_token_plain(character_id=character_id)
    if not rt:
        return None
    try:
        tr = await refresh_access_token(refresh_token=rt)
    except Exception:
        return None
    access = str(tr.get("access_token") or "")
    new_refresh = str(tr.get("refresh_token") or rt)
    if not access:
        return None
    scopes = str(tr.get("scope") or settings.sso_scopes)
    expires_in = tr.get("expires_in")
    access_expires_at = None
    if expires_in is not None:
        try:
            access_expires_at = datetime.now(UTC) + timedelta(seconds=int(expires_in))
        except (TypeError, ValueError):
            access_expires_at = None
    await upsert_eve_refresh_token(
        character_id=character_id,
        refresh_token=new_refresh,
        scopes=scopes,
        owner_user_id=owner_user_id,
        access_token=access,
        access_expires_at=access_expires_at,
    )
    return access


def _agg_add(m: dict[int, int], type_id: int, qty: int) -> None:
    if qty <= 0:
        return
    m[type_id] = m.get(type_id, 0) + qty


@dataclass
class MoonTaxLine:
    type_id: int
    type_name: str
    quantity: int
    adjusted_price_each: float | None
    value_isk: float | None


@dataclass
class MoonTaxContractRef:
    contract_id: int
    status: str
    type: str
    title: str
    date_issued: str | None


@dataclass
class MoonTaxSummary:
    ok: bool
    error: str = ""
    character_id: int = 0
    character_name: str = ""
    period_days: int = 30
    tax_assignee_id: int = 0
    mined_by_type: list[MoonTaxLine] = field(default_factory=list)
    contracted_to_tax_by_type: list[MoonTaxLine] = field(default_factory=list)
    assets_by_type: list[MoonTaxLine] = field(default_factory=list)
    owed_by_type: list[MoonTaxLine] = field(default_factory=list)
    mined_total_isk: float | None = None
    contracted_total_isk: float | None = None
    assets_total_isk: float | None = None
    owed_total_isk: float | None = None
    suggested_tax_isk: float | None = None
    contracts_matched: list[MoonTaxContractRef] = field(default_factory=list)
    payment_instructions: str = ""
    warnings: list[str] = field(default_factory=list)


_CONTRACT_OK_STATUS = frozenset(
    {
        "outstanding",
        "in_progress",
        "finished_issuer",
        "finished_contractor",
    }
)


async def compute_moon_tax_summary(
    *,
    discord_user_id: int,
    character_id: int | None,
    period_days: int,
    include_assets: bool,
) -> MoonTaxSummary:
    assignee = int(settings.moon_tax_assignee_id or 0)
    if assignee <= 0:
        return MoonTaxSummary(ok=False, error="moon_tax_assignee_id_unset")

    if not settings.database_url:
        return MoonTaxSummary(ok=False, error="database_unconfigured")

    days = max(1, min(90, int(period_days)))

    async with session_scope() as session:
        cu = await session.scalar(select(CoreUser).where(CoreUser.discord_user_id == discord_user_id))
        if cu is None:
            return MoonTaxSummary(ok=False, error="discord_not_linked")
        cid = character_id if character_id is not None else cu.main_character_id
        if cid is None:
            return MoonTaxSummary(ok=False, error="no_main_character")
        link = await session.get(EveLinkedCharacter, int(cid))
        if link is None or link.user_id != cu.id:
            return MoonTaxSummary(ok=False, error="character_not_linked_to_user")
        owner_uuid = cu.id
        char_name = link.character_name or ""

    bearer = await _access_token_for_character(character_id=int(cid), owner_user_id=owner_uuid)
    if not bearer:
        return MoonTaxSummary(ok=False, error="no_refresh_token_for_character")

    ch_public = await esi_get_json(f"/characters/{int(cid)}/")
    if ch_public and ch_public.get("name"):
        char_name = str(ch_public["name"])

    cutoff = datetime.now(UTC) - timedelta(days=days)
    prices = await _markets_adjusted_prices()

    warnings: list[str] = []

    # --- Mining ledger ---
    raw_ledger = await esi_get_paged_json_list(f"/characters/{int(cid)}/mining/ledger/", bearer=bearer)
    mined: dict[int, int] = {}
    for row in raw_ledger:
        if not isinstance(row, dict):
            continue
        dt = _parse_esi_dt(str(row.get("date") or ""))
        if dt is None or dt < cutoff:
            continue
        try:
            tid = int(row["type_id"])
            qty = int(row["quantity"])
        except (KeyError, TypeError, ValueError):
            continue
        _agg_add(mined, tid, qty)

    # --- Contracts to tax assignee (item_exchange you issued to the configured assignee) ---
    raw_contracts = await esi_get_paged_json_list(f"/characters/{int(cid)}/contracts/", bearer=bearer)
    contracted: dict[int, int] = {}
    matched_meta: list[MoonTaxContractRef] = []
    max_contract_items = 60

    qualified: list[tuple[int, dict[str, Any]]] = []
    for c in raw_contracts:
        if not isinstance(c, dict):
            continue
        try:
            c_id = int(c["contract_id"])
        except (KeyError, TypeError, ValueError):
            continue
        status = str(c.get("status") or "")
        ctype = str(c.get("type") or "")
        if ctype != "item_exchange":
            continue
        if status not in _CONTRACT_OK_STATUS:
            continue
        try:
            issuer = int(c.get("issuer_id") or 0)
            assignee_id = int(c.get("assignee_id") or 0)
        except (TypeError, ValueError):
            continue
        if issuer != int(cid) or assignee_id != assignee:
            continue
        di = _parse_esi_dt(str(c.get("date_issued") or ""))
        if di is None or di < cutoff:
            continue
        qualified.append((c_id, c))

    if len(qualified) > max_contract_items:
        warnings.append(
            f"Only the first {max_contract_items} of {len(qualified)} matching contracts were scanned for items."
        )

    for c_id, c in qualified[:max_contract_items]:
        status = str(c.get("status") or "")
        ctype = str(c.get("type") or "")
        matched_meta.append(
            MoonTaxContractRef(
                contract_id=c_id,
                status=status,
                type=ctype,
                title=str(c.get("title") or "")[:120],
                date_issued=str(c.get("date_issued") or "")[:32] or None,
            )
        )
        items = await esi_get_paged_json_list(
            f"/characters/{int(cid)}/contracts/{c_id}/items/",
            bearer=bearer,
        )
        for it in items:
            if not isinstance(it, dict):
                continue
            try:
                tid = int(it["type_id"])
                qty = int(it["quantity"])
            except (KeyError, TypeError, ValueError):
                continue
            is_included = bool(it.get("is_included", True))
            if not is_included:
                continue
            _agg_add(contracted, tid, qty)

    # --- Optional assets (root list only; quantities for rough “still in hangar”) ---
    assets: dict[int, int] = {}
    if include_assets:
        try:
            raw_assets = await esi_get_paged_json_list(f"/characters/{int(cid)}/assets/", bearer=bearer)
        except Exception as exc:
            warnings.append(f"assets_fetch_failed: {exc!r}")
            raw_assets = []
        for a in raw_assets:
            if not isinstance(a, dict):
                continue
            try:
                tid = int(a["type_id"])
                qty = int(a["quantity"])
            except (KeyError, TypeError, ValueError):
                continue
            if tid in mined or tid in contracted:
                _agg_add(assets, tid, qty)

    def _lines(m: dict[int, int], *, limit: int = 25) -> list[MoonTaxLine]:
        lines: list[MoonTaxLine] = []
        for tid, qty in sorted(m.items(), key=lambda kv: kv[0]):
            if len(lines) >= limit:
                break
            ap = prices.get(tid)
            val = float(qty) * ap if ap is not None else None
            lines.append(
                MoonTaxLine(
                    type_id=tid,
                    type_name="",
                    quantity=qty,
                    adjusted_price_each=ap,
                    value_isk=val,
                )
            )
        return lines

    mined_lines = _lines(mined, limit=40)
    for ln in mined_lines:
        ln.type_name = await _universe_type_name(ln.type_id)

    contracted_lines = _lines(contracted, limit=40)
    for ln in contracted_lines:
        ln.type_name = await _universe_type_name(ln.type_id)

    assets_lines = _lines(assets, limit=40)
    for ln in assets_lines:
        ln.type_name = await _universe_type_name(ln.type_id)

    owed: dict[int, int] = {}
    for tid, q in mined.items():
        left = q - contracted.get(tid, 0)
        if left > 0:
            owed[tid] = left

    owed_lines = _lines(owed, limit=40)
    for ln in owed_lines:
        ln.type_name = await _universe_type_name(ln.type_id)

    def _sum_isk(lines: list[MoonTaxLine]) -> float | None:
        if not lines:
            return 0.0
        s = 0.0
        n = 0
        for ln in lines:
            if ln.value_isk is not None:
                s += ln.value_isk
                n += 1
        if n == 0:
            return None
        return round(s, 2)

    mined_total = _sum_isk(mined_lines)
    contracted_total = _sum_isk(contracted_lines)
    assets_total = _sum_isk(assets_lines)
    owed_total = _sum_isk(owed_lines)

    pct = float(settings.moon_tax_percent_of_owed_value or 0.0)
    suggested = None
    if owed_total is not None and pct > 0:
        suggested = round(owed_total * (pct / 100.0), 2)

    instr = (settings.moon_tax_payment_instructions or "").strip()

    return MoonTaxSummary(
        ok=True,
        character_id=int(cid),
        character_name=char_name,
        period_days=days,
        tax_assignee_id=assignee,
        mined_by_type=mined_lines,
        contracted_to_tax_by_type=contracted_lines,
        assets_by_type=assets_lines,
        owed_by_type=owed_lines,
        mined_total_isk=mined_total,
        contracted_total_isk=contracted_total,
        assets_total_isk=assets_total,
        owed_total_isk=owed_total,
        suggested_tax_isk=suggested,
        contracts_matched=matched_meta[:25],
        payment_instructions=instr,
        warnings=warnings,
    )


def summary_to_dict(s: MoonTaxSummary) -> dict[str, Any]:
    def line_dict(x: MoonTaxLine) -> dict[str, Any]:
        return {
            "type_id": x.type_id,
            "type_name": x.type_name,
            "quantity": x.quantity,
            "adjusted_price_each": x.adjusted_price_each,
            "value_isk": None if x.value_isk is None else round(x.value_isk, 2),
        }

    def cref_dict(x: MoonTaxContractRef) -> dict[str, Any]:
        return {
            "contract_id": x.contract_id,
            "status": x.status,
            "type": x.type,
            "title": x.title,
            "date_issued": x.date_issued,
        }

    return {
        "ok": s.ok,
        "error": s.error,
        "character_id": s.character_id,
        "character_name": s.character_name,
        "period_days": s.period_days,
        "tax_assignee_id": s.tax_assignee_id,
        "mined_by_type": [line_dict(x) for x in s.mined_by_type],
        "contracted_to_tax_by_type": [line_dict(x) for x in s.contracted_to_tax_by_type],
        "assets_by_type": [line_dict(x) for x in s.assets_by_type],
        "owed_by_type": [line_dict(x) for x in s.owed_by_type],
        "mined_total_isk": s.mined_total_isk,
        "contracted_total_isk": s.contracted_total_isk,
        "assets_total_isk": s.assets_total_isk,
        "owed_total_isk": s.owed_total_isk,
        "suggested_tax_isk": s.suggested_tax_isk,
        "contracts_matched": [cref_dict(x) for x in s.contracts_matched],
        "payment_instructions": s.payment_instructions,
        "warnings": s.warnings,
    }
