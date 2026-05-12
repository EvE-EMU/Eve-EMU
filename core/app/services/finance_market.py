"""Finance plugin: structure market discovery and merged regional sell orders (ESI + SDE + stored tokens)."""

from __future__ import annotations

from datetime import UTC, datetime, timedelta
from typing import Any
from uuid import UUID

import httpx
from sqlalchemy import select

from app.config import settings
from app.db.models import CoreUser, EveLinkedCharacter, FinanceMarketStructure
from app.db.session import session_scope
from app.db.token_store import get_eve_refresh_token_plain, upsert_eve_refresh_token
from app.services.esi_http import esi_get_json
from app.services.eve_sso_http import refresh_access_token
from app.sde import repository as sde_repo

_ESI_BASE = "https://esi.evetech.net/latest"
_USER_AGENT = "EVE-EMU-Core/1.0 (+finance; https://github.com/eve-emu)"


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


def _ordered_linked_character_ids(*, main_character_id: int | None, linked_ids: list[int]) -> list[int]:
    if not linked_ids:
        return []
    if main_character_id is not None and main_character_id in linked_ids:
        return [main_character_id] + [i for i in linked_ids if i != main_character_id]
    return list(linked_ids)


async def _http_get_status(*, path: str, bearer: str | None = None) -> tuple[int, Any]:
    headers = {"Accept": "application/json", "User-Agent": _USER_AGENT}
    if bearer:
        headers["Authorization"] = f"Bearer {bearer}"
    url = path if path.startswith("http") else f"{_ESI_BASE}{path}"
    async with httpx.AsyncClient(timeout=35.0) as client:
        resp = await client.get(url, headers=headers)
    try:
        data = resp.json()
    except Exception:
        data = None
    return resp.status_code, data


async def _probe_structure_market(*, structure_id: int, bearer: str) -> int:
    tid = int(settings.finance_structure_probe_type_id or 34)
    path = f"/markets/structures/{structure_id}/?type_id={tid}&order_type=sell&page=1"
    status, _ = await _http_get_status(path=path, bearer=bearer)
    return status


async def _fetch_sell_orders_pages(
    *, rel_query_path: str, bearer: str | None, max_pages: int
) -> tuple[list[dict[str, Any]], bool]:
    """GET market orders with a page cap. ``had_more`` is True if ESI reports more pages after the cap."""
    headers = {"Accept": "application/json", "User-Agent": _USER_AGENT}
    if bearer:
        headers["Authorization"] = f"Bearer {bearer}"
    base_rel = rel_query_path
    sep = "&" if "?" in base_rel else "?"
    out: list[dict[str, Any]] = []
    had_more = False
    async with httpx.AsyncClient(timeout=45.0) as client:
        for page in range(1, max_pages + 1):
            url = f"{_ESI_BASE}{base_rel}{sep}page={page}"
            resp = await client.get(url, headers=headers)
            if resp.status_code == 404:
                break
            resp.raise_for_status()
            data = resp.json()
            if not isinstance(data, list):
                break
            for row in data:
                if isinstance(row, dict):
                    out.append(row)
            try:
                total_pages = int(resp.headers.get("X-Pages", "1"))
            except (TypeError, ValueError):
                total_pages = 1
            if page < total_pages and page == max_pages:
                had_more = True
            if page >= total_pages or not data:
                break
    return out, had_more


async def finance_search_types(*, q: str, limit: int) -> list[dict[str, Any]]:
    rows = await sde_repo.search_types(q=q, limit=limit)
    return [r.model_dump(mode="json") for r in rows]


async def finance_list_structures() -> list[dict[str, Any]]:
    async with session_scope() as session:
        rows = (
            await session.scalars(select(FinanceMarketStructure).order_by(FinanceMarketStructure.structure_id))
        ).all()
    return [
        {
            "structure_id": r.structure_id,
            "structure_name": r.structure_name,
            "solar_system_id": r.solar_system_id,
            "region_id": r.region_id,
            "witness_character_id": r.witness_character_id,
            "updated_at": r.updated_at.isoformat() if r.updated_at else None,
        }
        for r in rows
    ]


async def finance_contribute_structures(*, discord_user_id: int, structure_ids: list[int]) -> dict[str, Any]:
    if not settings.database_url:
        return {"ok": False, "error": "database_unconfigured", "results": []}

    async with session_scope() as session:
        cu = await session.scalar(select(CoreUser).where(CoreUser.discord_user_id == discord_user_id))
        if cu is None:
            return {"ok": False, "error": "discord_not_linked", "results": []}
        owner_uuid = cu.id
        main_id = cu.main_character_id
        stmt = select(EveLinkedCharacter.character_id).where(EveLinkedCharacter.user_id == cu.id)
        linked_ids = list((await session.scalars(stmt)).all())

    if not linked_ids:
        return {"ok": False, "error": "no_linked_characters", "results": []}

    order_ids = _ordered_linked_character_ids(main_character_id=main_id, linked_ids=linked_ids)
    results: list[dict[str, Any]] = []
    for sid in structure_ids:
        results.append(await _contribute_single_structure(structure_id=int(sid), owner_user_id=owner_uuid, try_character_ids=order_ids))
    ok_any = any(bool(r.get("ok")) for r in results)
    return {"ok": ok_any, "error": "" if ok_any else "all_failed", "results": results}


async def _contribute_single_structure(
    *,
    structure_id: int,
    owner_user_id: UUID,
    try_character_ids: list[int],
) -> dict[str, Any]:
    if structure_id <= 0:
        return {"structure_id": structure_id, "ok": False, "error": "invalid_id"}

    st_public = await esi_get_json(f"/universe/structures/{structure_id}/")
    if not st_public:
        status, _ = await _http_get_status(path=f"/universe/structures/{structure_id}/")
        if status == 404:
            return {"structure_id": structure_id, "ok": False, "error": "structure_not_found"}
        return {"structure_id": structure_id, "ok": False, "error": "universe_structure_failed"}

    name = str(st_public.get("name") or "").strip() or f"Structure {structure_id}"
    solar_system_id = st_public.get("solar_system_id")
    try:
        ssid = int(solar_system_id) if solar_system_id is not None else None
    except (TypeError, ValueError):
        ssid = None

    region_id: int | None = None
    if ssid is not None:
        sys_body = await esi_get_json(f"/universe/systems/{ssid}/")
        if sys_body and sys_body.get("region_id") is not None:
            try:
                region_id = int(sys_body["region_id"])
            except (TypeError, ValueError):
                region_id = None

    witness: int | None = None
    for ch_id in try_character_ids:
        bearer = await _access_token_for_character(character_id=int(ch_id), owner_user_id=owner_user_id)
        if not bearer:
            continue
        ps = await _probe_structure_market(structure_id=structure_id, bearer=bearer)
        if ps == 200:
            witness = int(ch_id)
            break

    if witness is None:
        return {
            "structure_id": structure_id,
            "ok": False,
            "error": "no_token_or_no_market_access",
            "structure_name": name,
            "region_id": region_id,
            "solar_system_id": ssid,
        }

    async with session_scope() as session:
        now = datetime.now(UTC)
        row = await session.get(FinanceMarketStructure, structure_id)
        if row:
            row.structure_name = name
            row.solar_system_id = ssid
            row.region_id = region_id
            row.witness_character_id = witness
            row.updated_at = now
        else:
            session.add(
                FinanceMarketStructure(
                    structure_id=structure_id,
                    structure_name=name,
                    solar_system_id=ssid,
                    region_id=region_id,
                    witness_character_id=witness,
                    updated_at=now,
                )
            )
        await session.commit()

    return {
        "structure_id": structure_id,
        "ok": True,
        "error": "",
        "structure_name": name,
        "region_id": region_id,
        "solar_system_id": ssid,
        "witness_character_id": witness,
    }


def _parse_order_row(row: dict[str, Any], *, source_kind: str, source_label: str) -> dict[str, Any] | None:
    if row.get("is_buy_order") is True:
        return None
    try:
        oid = int(row["order_id"])
        tid = int(row["type_id"])
        price = float(row["price"])
        vol = int(row.get("volume_remain") or 0)
        loc = int(row.get("location_id") or 0)
    except (KeyError, TypeError, ValueError):
        return None
    return {
        "order_id": oid,
        "type_id": tid,
        "price": price,
        "volume_remain": vol,
        "location_id": loc,
        "source_kind": source_kind,
        "source_label": source_label,
    }


async def finance_top_sells(*, type_id: int, region_id: int | None, limit: int) -> dict[str, Any]:
    if not settings.database_url:
        return {"ok": False, "error": "database_unconfigured"}

    rid = int(region_id if region_id is not None else settings.finance_default_region_id)
    max_lim = int(settings.finance_sells_max_limit or 50)
    lim = max(1, min(max_lim, int(limit)))

    type_row = await sde_repo.get_type_by_id(type_id)
    type_name = type_row.name if type_row else f"type {type_id}"

    max_reg_pages = int(settings.finance_region_orders_max_pages or 10)
    rel_reg = f"/markets/{rid}/orders/?type_id={type_id}&order_type=sell"
    reg_orders_raw, reg_more = await _fetch_sell_orders_pages(rel_query_path=rel_reg, bearer=None, max_pages=max_reg_pages)

    merged: list[dict[str, Any]] = []
    for row in reg_orders_raw:
        parsed = _parse_order_row(row, source_kind="region", source_label=f"NPC/stations (region {rid})")
        if parsed:
            merged.append(parsed)

    max_struct = int(settings.finance_sells_max_structure_sources or 40)
    max_spages = int(settings.finance_structure_orders_max_pages or 3)

    async with session_scope() as session:
        stmt = (
            select(FinanceMarketStructure)
            .where(FinanceMarketStructure.region_id == rid)
            .order_by(FinanceMarketStructure.structure_id)
            .limit(max_struct)
        )
        struct_rows = list((await session.scalars(stmt)).all())

    struct_notes: list[dict[str, Any]] = []
    struct_had_more = False

    for fr in struct_rows:
        witness = int(fr.witness_character_id)
        async with session_scope() as session:
            link = await session.get(EveLinkedCharacter, witness)
            if link is None:
                struct_notes.append({"structure_id": fr.structure_id, "error": "witness_not_linked"})
                continue
            owner_uid = link.user_id
        bearer = await _access_token_for_character(character_id=witness, owner_user_id=owner_uid)
        if not bearer:
            struct_notes.append({"structure_id": fr.structure_id, "error": "no_token"})
            continue
        rel_st = f"/markets/structures/{fr.structure_id}/?type_id={type_id}&order_type=sell"
        try:
            raw_st, more = await _fetch_sell_orders_pages(rel_query_path=rel_st, bearer=bearer, max_pages=max_spages)
        except Exception as exc:
            struct_notes.append({"structure_id": fr.structure_id, "error": f"esi_error:{type(exc).__name__}"})
            continue
        if more:
            struct_had_more = True
        label = (fr.structure_name or "").strip() or str(fr.structure_id)
        for row in raw_st:
            parsed = _parse_order_row(row, source_kind="structure", source_label=label)
            if parsed:
                merged.append(parsed)

    merged.sort(key=lambda x: float(x["price"]))
    truncated = bool(reg_more or struct_had_more or len(merged) > lim)
    top = merged[:lim]

    return {
        "ok": True,
        "error": "",
        "type_id": type_id,
        "type_name": type_name,
        "region_id": rid,
        "default_region_id": int(settings.finance_default_region_id),
        "orders": top,
        "truncated": truncated,
        "structure_source_count": len(struct_rows),
        "structure_notes": struct_notes,
    }
