"""Corp storefront — hangar inventory, Janice split pricing, WTB order flow."""

from __future__ import annotations

import json
import logging
import secrets
from decimal import Decimal
from typing import Any

import httpx
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.config import settings
from app.models import OrgSettings, SdeSystem
from app.models.member_audit import CharacterAsset, UniverseLocation
from app.models.storefront import (
    StorefrontConfig,
    StorefrontItemOverride,
    StorefrontKit,
    StorefrontOrder,
    StorefrontPickupLocation,
)
from app.models.tools import LinkedCharacter, SsoUser
from app.services.audit_scopes import has_corp_assets_access, parse_granted_scopes
from app.services.eve_mail import send_character_mail
from app.services.janice import JANICE_MARKETS, janice_configured, janice_prices_by_type_id
from app.services.sde_search import get_type
from app.services.structure_sync import is_structure_id

logger = logging.getLogger(__name__)
_UA = "EVE-EMU-EMUMS/1.0 (+https://emums.eve-emu.com; storefront)"


def _parse_character_ids(raw: str) -> list[int]:
    out: list[int] = []
    for part in (raw or "").split(","):
        part = part.strip()
        if not part:
            continue
        try:
            out.append(int(part))
        except ValueError:
            continue
    return out


async def get_storefront_config(session: AsyncSession) -> StorefrontConfig:
    row = await session.scalar(select(StorefrontConfig).limit(1))
    if row:
        return row
    row = StorefrontConfig(
        corp_name="Solar Extraction Venture",
        corp_id=98829530,
        corp_hangar_flag="CorpSAG1",
        structure_name_contains="",
        system_name_contains="",
        price_hub="jita",
        staff_notify_character_id=int(settings.corp_market_notify_character_id or 0),
    )
    session.add(row)
    await session.flush()
    return row


async def ensure_storefront_defaults(session: AsyncSession) -> None:
    cfg = await get_storefront_config(session)
    loc_count = await session.scalar(select(func.count()).select_from(StorefrontPickupLocation))
    if not loc_count:
        session.add(
            StorefrontPickupLocation(
                label="Corp hangar (default)",
                structure_name=(settings.wompstar_structure_name or "").strip() or "Corp structure",
                structure_id=int(settings.wompstar_structure_id or 0),
                system_name="",
                location_hint="Corp Hangar Division 1 — confirm structure in-game with staff.",
                is_default=True,
                active=True,
                sort_order=0,
            )
        )
    if not cfg.staff_notify_character_id and settings.corp_market_notify_character_id:
        cfg.staff_notify_character_id = int(settings.corp_market_notify_character_id)
    if not int(cfg.corp_id or 0):
        cfg.corp_id = 98829530
    # Legacy defaults scoped one structure — corp stock is all structures with hangar 1.
    if (
        int(cfg.corp_id or 0) == 98829530
        and (cfg.structure_name_contains or "").strip() == "Engineering Yard"
        and (cfg.system_name_contains or "").strip() == "3-F"
        and not int(cfg.structure_id or 0)
    ):
        cfg.structure_name_contains = ""
        cfg.system_name_contains = ""
    await session.flush()


def _has_location_filters(cfg: StorefrontConfig) -> bool:
    return bool(
        int(cfg.structure_id or 0) > 0
        or (cfg.structure_name_contains or "").strip()
        or (cfg.system_name_contains or "").strip()
    )


async def _inventory_character_ids(session: AsyncSession, cfg: StorefrontConfig) -> list[int]:
    raw = (cfg.inventory_character_ids or "").strip()
    if raw:
        out: list[int] = []
        for part in raw.split(","):
            part = part.strip()
            if not part:
                continue
            try:
                out.append(int(part))
                continue
            except ValueError:
                pass
            for model in (SsoUser, LinkedCharacter):
                cid = await session.scalar(
                    select(model.character_id).where(model.character_name.ilike(part)).limit(1)
                )
                if cid:
                    out.append(int(cid))
                    break
        return list(dict.fromkeys(out))

    corp_id = int(cfg.corp_id or 0)
    if not corp_id:
        return []
    ids: set[int] = set()
    for cid in (
        await session.scalars(select(SsoUser.character_id).where(SsoUser.corporation_id == corp_id))
    ).all():
        ids.add(int(cid))
    for cid in (
        await session.scalars(
            select(LinkedCharacter.character_id).where(LinkedCharacter.corporation_id == corp_id)
        )
    ).all():
        ids.add(int(cid))
    return sorted(ids)


async def _resolve_inventory_location_ids(session: AsyncSession, cfg: StorefrontConfig) -> set[int]:
    ids: set[int] = set()
    if int(cfg.structure_id or 0) > 0:
        ids.add(int(cfg.structure_id))
    name_part = (cfg.structure_name_contains or "").strip()
    sys_part = (cfg.system_name_contains or "").strip()
    if not name_part and not sys_part and not ids:
        return ids

    q = select(UniverseLocation.entity_id)
    if name_part:
        q = q.where(UniverseLocation.name.ilike(f"%{name_part}%"))
    if sys_part:
        sys_ids = (
            await session.scalars(select(SdeSystem.system_id).where(SdeSystem.name.ilike(f"%{sys_part}%")))
        ).all()
        if sys_ids:
            q = q.where(UniverseLocation.solar_system_id.in_(sys_ids))
    for eid in (await session.scalars(q)).all():
        ids.add(int(eid))
    return ids


async def _synced_inventory(session: AsyncSession, cfg: StorefrontConfig) -> dict[int, dict[str, Any]]:
    char_ids = await _inventory_character_ids(session, cfg)
    if not char_ids:
        return {}

    flag = (cfg.corp_hangar_flag or "CorpSAG1").strip()
    loc_ids: set[int] | None = None
    if _has_location_filters(cfg):
        loc_ids = await _resolve_inventory_location_ids(session, cfg)

    rows = (
        await session.scalars(
            select(CharacterAsset).where(
                CharacterAsset.character_id.in_(char_ids),
                CharacterAsset.flag == flag,
            )
        )
    ).all()

    # Dedupe by item_id — multiple corp characters may sync the same hangar.
    by_item: dict[int, CharacterAsset] = {}
    structure_ids: set[int] = set()
    for asset in rows:
        lid = int(asset.location_id or 0)
        if not is_structure_id(lid):
            continue
        if loc_ids is not None and lid not in loc_ids:
            continue
        structure_ids.add(lid)
        item_id = int(asset.item_id or 0)
        if item_id <= 0:
            continue
        prev = by_item.get(item_id)
        if not prev or (asset.synced_at and (not prev.synced_at or asset.synced_at >= prev.synced_at)):
            by_item[item_id] = asset

    out: dict[int, dict[str, Any]] = {}
    for asset in by_item.values():
        tid = int(asset.type_id)
        bucket = out.setdefault(
            tid,
            {
                "type_id": tid,
                "type_name": str(asset.type_name or f"Type {tid}"),
                "synced_qty": 0,
                "structure_ids": set(),
            },
        )
        bucket["synced_qty"] += int(asset.quantity or 0)
        bucket["structure_ids"].add(int(asset.location_id or 0))

    for tid, bucket in out.items():
        bucket["structure_count"] = len(bucket.pop("structure_ids", set()))
    return out


async def _override_map(session: AsyncSession) -> dict[int, StorefrontItemOverride]:
    rows = (await session.scalars(select(StorefrontItemOverride))).all()
    return {int(r.type_id): r for r in rows}


async def _price_map(session: AsyncSession, cfg: StorefrontConfig, type_ids: set[int]) -> dict[int, dict[str, Any]]:
    if not type_ids:
        return {}
    overrides = await _override_map(session)
    out: dict[int, dict[str, Any]] = {}
    need_market: set[int] = set()

    for tid in type_ids:
        ov = overrides.get(tid)
        if ov and ov.price_override_isk is not None:
            price = float(ov.price_override_isk)
            out[tid] = {
                "unit_price_isk": price,
                "janice_split_isk": None,
                "janice_sell_isk": None,
                "janice_buy_isk": None,
                "price_source": "override",
            }
        else:
            need_market.add(tid)

    if need_market and janice_configured():
        hub = (cfg.price_hub or "jita").lower()
        janice_rows = await janice_prices_by_type_id(sorted(need_market), market=hub)
        still_need: set[int] = set()
        for tid in need_market:
            row = janice_rows.get(tid) or {}
            split = row.get("split")
            sell = row.get("sell")
            buy = row.get("buy")
            unit = None
            source = "unpriced"
            if split is not None and float(split) > 0:
                unit = float(split)
                source = "janice_split"
            elif sell is not None and float(sell) > 0:
                unit = float(sell)
                source = "janice_sell"
            elif buy is not None and float(buy) > 0:
                unit = float(buy)
                source = "janice_buy"
            else:
                still_need.add(tid)
            out[tid] = {
                "unit_price_isk": unit,
                "janice_split_isk": float(split) if split is not None else None,
                "janice_sell_isk": float(sell) if sell is not None else None,
                "janice_buy_isk": float(buy) if buy is not None else None,
                "price_source": source,
            }
        # Final fallback: hub market aggregates (ESI / Janice pricer path).
        if still_need:
            from app.services.market_prices import hub_prices_for_types

            hub_prices, _src = await hub_prices_for_types(session, still_need, hub=hub)
            for tid in still_need:
                hp = hub_prices.get(tid) or {}
                sell = hp.get("sell")
                buy = hp.get("buy")
                unit = None
                source = "unpriced"
                if sell is not None and float(sell) > 0:
                    unit = float(sell)
                    source = "market_sell"
                elif buy is not None and float(buy) > 0:
                    unit = float(buy)
                    source = "market_buy"
                prev = out.get(tid) or {}
                out[tid] = {
                    **prev,
                    "unit_price_isk": unit,
                    "price_source": source,
                }
    elif need_market:
        from app.services.market_prices import hub_prices_for_types

        hub = (cfg.price_hub or "jita").lower()
        hub_prices, _src = await hub_prices_for_types(session, need_market, hub=hub)
        for tid in need_market:
            hp = hub_prices.get(tid) or {}
            sell = hp.get("sell")
            buy = hp.get("buy")
            unit = None
            source = "janice_unconfigured"
            if sell is not None and float(sell) > 0:
                unit = float(sell)
                source = "market_sell"
            elif buy is not None and float(buy) > 0:
                unit = float(buy)
                source = "market_buy"
            out[tid] = {
                "unit_price_isk": unit,
                "janice_split_isk": None,
                "janice_sell_isk": float(sell) if sell is not None else None,
                "janice_buy_isk": float(buy) if buy is not None else None,
                "price_source": source,
            }
    return out


def _catalog_item_row(
    *,
    kind: str,
    key: str,
    name: str,
    type_id: int | None,
    kit_id: int | None,
    quantity: int,
    synced_qty: int,
    fake_qty_add: int,
    unit_price: float | None,
    janice_split: float | None,
    price_source: str,
    hidden: bool,
    note: str = "",
    kit_items: list[dict[str, Any]] | None = None,
    group_name: str = "",
    category_name: str = "",
    low_stock: bool = False,
) -> dict[str, Any]:
    return {
        "key": key,
        "kind": kind,
        "type_id": type_id,
        "kit_id": kit_id,
        "name": name,
        "quantity": quantity,
        "synced_qty": synced_qty,
        "fake_qty_add": fake_qty_add,
        "unit_price_isk": unit_price,
        "janice_split_isk": janice_split,
        "price_source": price_source,
        "price_label": "Contact to order" if unit_price is None else None,
        "hidden": hidden,
        "note": note,
        "kit_items": kit_items or [],
        "group_name": group_name,
        "category_name": category_name,
        "low_stock": low_stock,
        "line_total_isk": (float(unit_price) * quantity) if unit_price is not None else None,
    }


async def build_catalog(
    session: AsyncSession, *, include_hidden: bool = False, public: bool = False
) -> dict[str, Any]:
    from app.models.tools import SdeTypeIndex

    cfg = await get_storefront_config(session)
    overrides = await _override_map(session)
    synced = await _synced_inventory(session, cfg)

    type_ids: set[int] = set(synced.keys()) | set(overrides.keys())
    prices = await _price_map(session, cfg, type_ids)

    sde_meta: dict[int, SdeTypeIndex] = {}
    if type_ids:
        for row in (
            await session.scalars(select(SdeTypeIndex).where(SdeTypeIndex.type_id.in_(type_ids)))
        ).all():
            sde_meta[int(row.type_id)] = row

    items: list[dict[str, Any]] = []
    qty_by_type: dict[int, int] = {}
    for tid in sorted(type_ids):
        ov = overrides.get(tid)
        if ov and ov.hidden and not include_hidden:
            continue
        base = synced.get(tid, {})
        synced_qty = int(base.get("synced_qty") or 0)
        fake_add = int(ov.fake_qty_add if ov else 0)
        qty = synced_qty + fake_add
        if qty <= 0 and not include_hidden:
            continue
        if qty <= 0 and include_hidden and not ov:
            continue

        meta = sde_meta.get(tid)
        tname = (ov.type_name if ov and ov.type_name else base.get("type_name")) or (
            meta.name if meta else f"Type {tid}"
        )
        if not (ov and ov.type_name) and not base.get("type_name") and not meta:
            row = await get_type(session, tid)
            if row:
                tname = row["name"]

        price = prices.get(tid, {})
        unit = price.get("unit_price_isk")
        qty_by_type[tid] = qty
        items.append(
            _catalog_item_row(
                kind="item",
                key=f"item:{tid}",
                name=tname,
                type_id=tid,
                kit_id=None,
                quantity=qty,
                synced_qty=synced_qty,
                fake_qty_add=fake_add,
                unit_price=unit,
                janice_split=price.get("janice_split_isk"),
                price_source=str(price.get("price_source") or "unknown"),
                hidden=bool(ov.hidden if ov else False),
                note=(ov.note if ov else "") or "",
                group_name=(meta.group_name if meta else "") or "",
                category_name=(meta.category_name if meta else "") or "",
                low_stock=qty > 0 and qty < 10,
            )
        )

    kits = (
        await session.scalars(
            select(StorefrontKit)
            .options(selectinload(StorefrontKit.items))
            .where(StorefrontKit.active.is_(True))
            .order_by(StorefrontKit.sort_order, StorefrontKit.name)
        )
    ).all()
    if include_hidden:
        kits = (
            await session.scalars(
                select(StorefrontKit).options(selectinload(StorefrontKit.items)).order_by(StorefrontKit.sort_order)
            )
        ).all()

    for kit in kits:
        if not kit.active and not include_hidden:
            continue
        kit_items = [
            {
                "type_id": int(i.type_id),
                "type_name": i.type_name,
                "quantity": int(i.quantity),
            }
            for i in kit.items
        ]
        # Kits available = min floor of component stock / component qty.
        kit_qty = None
        kit_price_parts = Decimal("0")
        kit_price_ok = True
        for comp in kit_items:
            ctid = int(comp.get("type_id") or 0)
            need = max(1, int(comp.get("quantity") or 1))
            avail = int(qty_by_type.get(ctid, 0))
            can_make = avail // need
            kit_qty = can_make if kit_qty is None else min(kit_qty, can_make)
            unit = (prices.get(ctid) or {}).get("unit_price_isk")
            if unit is None:
                kit_price_ok = False
            else:
                kit_price_parts += Decimal(str(unit)) * need
        if kit_qty is None:
            kit_qty = 0
        if kit.price_isk is not None:
            price = float(kit.price_isk)
            price_source = "manual"
        elif kit_price_ok and kit_items:
            price = float(kit_price_parts)
            price_source = "components"
        else:
            price = None
            price_source = "contact"
        if kit_qty <= 0 and not include_hidden:
            continue
        items.append(
            _catalog_item_row(
                kind="kit",
                key=f"kit:{kit.id}",
                name=kit.name,
                type_id=None,
                kit_id=int(kit.id),
                quantity=int(kit_qty),
                synced_qty=int(kit_qty),
                fake_qty_add=0,
                unit_price=price,
                janice_split=None,
                price_source=price_source,
                hidden=False,
                note=kit.description or "",
                kit_items=kit_items,
                group_name="Kits",
                category_name="Kits",
                low_stock=kit_qty > 0 and kit_qty < 3,
            )
        )

    locations = (
        await session.scalars(
            select(StorefrontPickupLocation)
            .where(StorefrontPickupLocation.active.is_(True))
            .order_by(StorefrontPickupLocation.sort_order, StorefrontPickupLocation.label)
        )
    ).all()

    hub = (cfg.price_hub or "jita").lower()
    hub_label = JANICE_MARKETS.get(hub, (0, hub))[1]
    char_ids = await _inventory_character_ids(session, cfg)
    corp_assets_scope_count = 0
    for cid in char_ids:
        user = await session.scalar(select(SsoUser).where(SsoUser.character_id == cid))
        if user and has_corp_assets_access(parse_granted_scopes(user.scopes_json)):
            corp_assets_scope_count += 1
    inventory_source: dict[str, Any] = {
        "corp_id": int(cfg.corp_id or 0),
        "corp_hangar_flag": cfg.corp_hangar_flag,
        "corp_hangar_division": 1 if (cfg.corp_hangar_flag or "") == "CorpSAG1" else cfg.corp_hangar_flag,
        "scope": "all_corp_structures" if not _has_location_filters(cfg) else "filtered_structures",
        "sync_character_count": len(char_ids),
        "sync_hangar_type_count": len(synced),
        "sync_hangar_qty_total": sum(int(b.get("synced_qty") or 0) for b in synced.values()),
        "corp_assets_scope_count": corp_assets_scope_count,
    }
    if not public:
        inventory_source["structure_name_contains"] = cfg.structure_name_contains
        inventory_source["system_name_contains"] = cfg.system_name_contains
        inventory_source["structure_id"] = int(cfg.structure_id or 0)
        inventory_source["inventory_character_ids"] = char_ids

    priced = sum(1 for i in items if i.get("unit_price_isk") is not None)
    categories = sorted({str(i.get("category_name") or "Other") for i in items})
    return {
        "enabled": bool(cfg.enabled),
        "corp_name": cfg.corp_name,
        "price_hub": hub,
        "price_hub_label": hub_label,
        "pricing_source": (
            f"Janice split → sell → buy ({hub_label})"
            if janice_configured()
            else f"market sell/buy ({hub_label}) + overrides"
        ),
        "janice_configured": janice_configured(),
        "items": items,
        "pickup_locations": [_location_out(loc) for loc in locations],
        "inventory_source": inventory_source,
        "summary": {
            "item_count": len(items),
            "priced_count": priced,
            "unpriced_count": len(items) - priced,
            "total_stock_units": sum(int(i.get("quantity") or 0) for i in items if i.get("kind") == "item"),
            "kit_count": sum(1 for i in items if i.get("kind") == "kit"),
            "categories": categories,
            "low_stock_count": sum(1 for i in items if i.get("low_stock")),
        },
    }


def _location_out(loc: StorefrontPickupLocation) -> dict[str, Any]:
    return {
        "id": loc.id,
        "label": loc.label,
        "structure_name": loc.structure_name,
        "structure_id": int(loc.structure_id or 0),
        "system_name": loc.system_name,
        "location_hint": loc.location_hint,
        "is_default": bool(loc.is_default),
        "active": bool(loc.active),
        "sort_order": int(loc.sort_order or 0),
    }


def _config_out(cfg: StorefrontConfig) -> dict[str, Any]:
    return {
        "id": cfg.id,
        "enabled": bool(cfg.enabled),
        "corp_name": cfg.corp_name,
        "corp_id": int(cfg.corp_id or 0),
        "inventory_character_ids": cfg.inventory_character_ids,
        "corp_hangar_flag": cfg.corp_hangar_flag,
        "structure_id": int(cfg.structure_id or 0),
        "structure_name_contains": cfg.structure_name_contains,
        "system_name_contains": cfg.system_name_contains,
        "price_hub": cfg.price_hub,
        "discord_webhook_url": cfg.discord_webhook_url,
        "staff_notify_character_id": int(cfg.staff_notify_character_id or 0),
        "contract_expiration_hours": int(cfg.contract_expiration_hours or 24),
    }


async def list_pickup_locations_admin(session: AsyncSession) -> list[dict[str, Any]]:
    rows = (
        await session.scalars(
            select(StorefrontPickupLocation).order_by(
                StorefrontPickupLocation.sort_order, StorefrontPickupLocation.label
            )
        )
    ).all()
    return [_location_out(r) for r in rows]


async def list_overrides_admin(session: AsyncSession) -> list[dict[str, Any]]:
    rows = (await session.scalars(select(StorefrontItemOverride).order_by(StorefrontItemOverride.type_name))).all()
    return [
        {
            "id": r.id,
            "type_id": r.type_id,
            "type_name": r.type_name,
            "price_override_isk": float(r.price_override_isk) if r.price_override_isk is not None else None,
            "fake_qty_add": r.fake_qty_add,
            "hidden": r.hidden,
            "note": r.note,
        }
        for r in rows
    ]


def _kit_out(kit: StorefrontKit) -> dict[str, Any]:
    return {
        "id": kit.id,
        "name": kit.name,
        "description": kit.description,
        "price_isk": float(kit.price_isk) if kit.price_isk is not None else None,
        "active": kit.active,
        "sort_order": kit.sort_order,
        "items": [
            {"type_id": i.type_id, "type_name": i.type_name, "quantity": i.quantity}
            for i in kit.items
        ],
    }


async def list_kits_admin(session: AsyncSession) -> list[dict[str, Any]]:
    rows = (
        await session.scalars(
            select(StorefrontKit).options(selectinload(StorefrontKit.items)).order_by(StorefrontKit.sort_order)
        )
    ).all()
    return [_kit_out(k) for k in rows]


async def list_orders_admin(session: AsyncSession, *, limit: int = 100) -> list[dict[str, Any]]:
    cfg = await get_storefront_config(session)
    corp_name = cfg.corp_name or "Solar Extraction Venture"
    rows = (
        await session.scalars(
            select(StorefrontOrder).order_by(StorefrontOrder.created_at.desc()).limit(limit)
        )
    ).all()
    return [_order_out(o, corp_name=corp_name) for o in rows]


async def list_orders_for_buyer(
    session: AsyncSession, *, buyer_character_id: int, limit: int = 25
) -> list[dict[str, Any]]:
    cfg = await get_storefront_config(session)
    corp_name = cfg.corp_name or "Solar Extraction Venture"
    rows = (
        await session.scalars(
            select(StorefrontOrder)
            .where(StorefrontOrder.buyer_character_id == int(buyer_character_id))
            .order_by(StorefrontOrder.created_at.desc())
            .limit(limit)
        )
    ).all()
    return [_order_out(o, corp_name=corp_name) for o in rows]


def _order_out(order: StorefrontOrder, *, corp_name: str = "Solar Extraction Venture") -> dict[str, Any]:
    try:
        lines = json.loads(order.lines_json or "[]")
    except json.JSONDecodeError:
        lines = []
    return {
        "id": order.id,
        "order_code": order.order_code,
        "buyer_character_id": int(order.buyer_character_id or 0),
        "buyer_character_name": order.buyer_character_name,
        "pickup_location_id": order.pickup_location_id,
        "pickup_label": order.pickup_label,
        "lines": lines,
        "total_isk": float(order.total_isk),
        "contract_description": order.contract_description,
        "status": order.status,
        "mail_sent_buyer": order.mail_sent_buyer,
        "mail_sent_corp": order.mail_sent_corp,
        "discord_sent": order.discord_sent,
        "webhook_sent": order.webhook_sent,
        "mail_error": order.mail_error or None,
        "notes": order.notes,
        "created_at": order.created_at.isoformat() if order.created_at else None,
        "contract_instructions": _contract_instructions_from_order(order, lines, corp_name=corp_name),
    }


def _contract_instructions_from_order(
    order: StorefrontOrder, lines: list[dict[str, Any]], *, corp_name: str
) -> dict[str, Any]:
    item_lines = "\n".join(
        f"- {line.get('name')} x{int(line.get('quantity') or 0):,}"
        + (
            f" @ {float(line.get('unit_price_isk') or 0):,.2f} ISK"
            if line.get("unit_price_isk") is not None
            else ""
        )
        for line in lines
    )
    return {
        "type": "Item Exchange (WTB)",
        "description": order.contract_description,
        "i_will_pay": float(order.total_isk),
        "i_will_receive": "Items listed below",
        "items": item_lines,
        "steps": [
            "Open Contracts → Create Contract → Item Exchange.",
            f"Pickup: {order.pickup_label}.",
            f"Assignee: Corporation ({corp_name}) — confirm corp name in-game.",
            f"I will pay: {float(order.total_isk):,.2f} ISK.",
            "I will receive: the items listed (corp delivers from hangar).",
            f"Description (copy exactly): {order.contract_description}",
            "Set expiration as instructed in your confirmation mail.",
            "Staff will accept once your contract is live.",
        ],
    }


async def _post_discord(webhook_url: str, content: str) -> bool:
    if not webhook_url.strip():
        return False
    try:
        async with httpx.AsyncClient(timeout=15.0) as client:
            resp = await client.post(
                webhook_url.strip(),
                json={"content": content[:1900]},
                headers={"User-Agent": _UA},
            )
        return resp.status_code in (200, 204)
    except Exception:
        logger.exception("storefront discord webhook failed")
        return False


async def _send_storefront_order_notifications(
    session: AsyncSession,
    *,
    cfg: StorefrontConfig,
    order: StorefrontOrder,
    pickup: StorefrontPickupLocation,
    order_lines: list[dict[str, Any]],
    total: Decimal,
    notes: str,
) -> None:
    order_code = order.order_code
    item_block = "\n".join(
        f"- {line['name']} x{line['quantity']:,} @ {line['unit_price_isk']:,.2f} ISK "
        f"({line['total_isk']:,.2f} ISK)"
        for line in order_lines
    )
    hours = int(cfg.contract_expiration_hours or 24)
    corp_name = cfg.corp_name or "Solar Extraction Venture"

    buyer_body = (
        f"Storefront order {order_code}\n\n"
        f"Total: {float(total):,.2f} ISK\n"
        f"Pickup: {pickup.label} — {pickup.structure_name}\n"
        f"{pickup.location_hint}\n\n"
        f"Create an Item Exchange contract (WTB) to {corp_name}:\n\n"
        f"1. Contracts → Create → Item Exchange\n"
        f"2. Location: {pickup.structure_name} ({pickup.system_name})\n"
        f"3. Assignee: Corporation ({corp_name})\n"
        f"4. I will pay: {float(total):,.2f} ISK\n"
        f"5. I will receive: items below (0 ISK from corp)\n"
        f"6. Description (copy exactly): {order.contract_description}\n"
        f"7. Expiration: ~{hours} hours\n\n"
        f"Items:\n{item_block}\n\n"
        f"Staff will accept and deliver from corp hangar once your contract is issued.\n"
        f"— {settings.app_name}"
    )

    staff_body = (
        f"[Staff] Storefront order {order_code}\n\n"
        f"Buyer: {order.buyer_character_name} ({order.buyer_character_id})\n"
        f"Pickup: {pickup.label}\n"
        f"Total: {float(total):,.2f} ISK\n\n"
        f"Items:\n{item_block}\n\n"
        f"Contract description to match: {order.contract_description}\n"
        f"Prepare hangar pull / accept buyer WTB contract.\n"
    )
    if notes.strip():
        staff_body += f"\nBuyer notes: {notes.strip()}\n"

    mail_errors: list[str] = []
    buyer_id = int(order.buyer_character_id or 0)
    if buyer_id:
        ok, err = await send_character_mail(
            session,
            recipient_character_id=buyer_id,
            subject=f"Storefront order {order_code}",
            body=buyer_body,
        )
        order.mail_sent_buyer = ok
        if err:
            mail_errors.append(f"buyer: {err}")
    else:
        mail_errors.append("buyer: no character ID")

    notify_id = int(cfg.staff_notify_character_id or 0) or int(settings.corp_market_notify_character_id or 0)
    if notify_id:
        ok, err = await send_character_mail(
            session,
            recipient_character_id=notify_id,
            subject=f"[Staff] Storefront {order_code}",
            body=staff_body,
        )
        order.mail_sent_corp = ok
        if err:
            mail_errors.append(f"staff: {err}")

    org = await session.scalar(select(OrgSettings).limit(1))
    webhook = (cfg.discord_webhook_url or "").strip() or (org.discord_webhook_url if org else "")
    discord_msg = (
        f"**New Storefront order `{order_code}`**\n"
        f"Buyer: **{order.buyer_character_name}** (`{order.buyer_character_id}`)\n"
        f"Pickup: **{pickup.label}** ({pickup.structure_name})\n"
        f"Total: **{float(total):,.2f} ISK**\n\n"
        f"{item_block}\n\n"
        f"**Contract description:** `{order.contract_description}`\n"
        f"Action: prepare items / accept buyer Item Exchange WTB contract."
    )
    if webhook:
        order.discord_sent = await _post_discord(webhook, discord_msg)
        order.webhook_sent = order.discord_sent

    order.mail_error = "; ".join(mail_errors)[:2000]


def _catalog_qty(catalog_by_key: dict[str, dict[str, Any]], type_id: int) -> int:
    row = catalog_by_key.get(f"item:{type_id}")
    return int(row.get("quantity") or 0) if row else 0


async def submit_storefront_order(
    session: AsyncSession,
    *,
    buyer_character_id: int,
    buyer_character_name: str,
    pickup_location_id: int | None,
    cart_lines: list[dict[str, Any]],
    notes: str = "",
    notify: bool = True,
) -> dict[str, Any]:
    cfg = await get_storefront_config(session)
    if not cfg.enabled:
        return {"error": "disabled", "message": "Storefront is currently disabled."}

    catalog = await build_catalog(session)
    catalog_by_key = {item["key"]: item for item in catalog["items"]}

    pickup: StorefrontPickupLocation | None = None
    if pickup_location_id:
        pickup = await session.get(StorefrontPickupLocation, pickup_location_id)
        if not pickup or not pickup.active:
            return {"error": "invalid_location", "message": "Pickup location not available."}
    else:
        pickup = await session.scalar(
            select(StorefrontPickupLocation)
            .where(StorefrontPickupLocation.active.is_(True))
            .order_by(StorefrontPickupLocation.is_default.desc(), StorefrontPickupLocation.sort_order)
            .limit(1)
        )
    if not pickup:
        return {"error": "no_location", "message": "No pickup location configured."}

    order_lines: list[dict[str, Any]] = []
    total = Decimal("0")

    for cart in cart_lines:
        key = str(cart.get("key") or "")
        qty = int(cart.get("quantity") or 0)
        if qty < 1 or not key:
            continue
        item = catalog_by_key.get(key)
        if not item:
            return {"error": "invalid_item", "message": f"Unknown catalog item: {key}"}
        if item.get("hidden"):
            return {"error": "invalid_item", "message": f"Item not available: {item.get('name')}"}
        if item.get("kind") == "kit":
            for comp in item.get("kit_items") or []:
                need = int(comp.get("quantity") or 0) * qty
                avail = _catalog_qty(catalog_by_key, int(comp.get("type_id") or 0))
                if need > avail:
                    cname = comp.get("type_name") or f"Type {comp.get('type_id')}"
                    return {
                        "error": "insufficient_stock",
                        "message": (
                            f"Kit {item.get('name')}: not enough {cname} "
                            f"(need {need:,}, have {avail:,})."
                        ),
                    }
        if qty > int(item.get("quantity") or 0):
            return {
                "error": "insufficient_stock",
                "message": f"Not enough stock for {item.get('name')} (have {item.get('quantity')}, want {qty}).",
            }
        unit = item.get("unit_price_isk")
        if unit is None:
            return {
                "error": "unpriced",
                "message": f"{item.get('name')} requires contact to order — remove it or ask staff for pricing.",
            }
        line_total = Decimal(str(unit)) * qty
        total += line_total
        order_lines.append(
            {
                "key": key,
                "kind": item.get("kind"),
                "type_id": item.get("type_id"),
                "kit_id": item.get("kit_id"),
                "name": item.get("name"),
                "quantity": qty,
                "unit_price_isk": float(unit),
                "total_isk": float(line_total),
                "kit_items": item.get("kit_items") or [],
            }
        )

    if not order_lines:
        return {"error": "empty_cart", "message": "Cart is empty."}

    order_code = f"SF-{secrets.token_hex(4).upper()}"
    contract_description = f"EMUMS {order_code}"

    order = StorefrontOrder(
        order_code=order_code,
        buyer_character_id=int(buyer_character_id or 0),
        buyer_character_name=buyer_character_name.strip(),
        pickup_location_id=pickup.id,
        pickup_label=pickup.label,
        lines_json=json.dumps(order_lines),
        total_isk=total,
        contract_description=contract_description,
        status="pending",
        notes=notes.strip(),
    )
    session.add(order)
    await session.flush()

    if notify:
        await _send_storefront_order_notifications(
            session,
            cfg=cfg,
            order=order,
            pickup=pickup,
            order_lines=order_lines,
            total=total,
            notes=notes,
        )

    corp_name = cfg.corp_name or "Solar Extraction Venture"
    result = _order_out(order, corp_name=corp_name)
    return result


async def notify_storefront_order(session: AsyncSession, order_id: int) -> dict[str, Any]:
    """Send mail/Discord for an existing order (after commit)."""
    order = await session.get(StorefrontOrder, order_id)
    if not order:
        return {"error": "not_found", "message": "Order not found."}
    cfg = await get_storefront_config(session)
    pickup = await session.get(StorefrontPickupLocation, order.pickup_location_id or 0)
    if not pickup:
        pickup = await session.scalar(
            select(StorefrontPickupLocation)
            .where(StorefrontPickupLocation.active.is_(True))
            .order_by(StorefrontPickupLocation.is_default.desc())
            .limit(1)
        )
    if not pickup:
        return {"error": "no_location", "message": "Pickup location missing."}
    try:
        order_lines = json.loads(order.lines_json or "[]")
    except json.JSONDecodeError:
        order_lines = []
    await _send_storefront_order_notifications(
        session,
        cfg=cfg,
        order=order,
        pickup=pickup,
        order_lines=order_lines,
        total=Decimal(str(order.total_isk)),
        notes=order.notes or "",
    )
    return _order_out(order, corp_name=cfg.corp_name or "Solar Extraction Venture")


async def storefront_listing_for_type(session: AsyncSession, type_id: int) -> dict[str, Any] | None:
    catalog = await build_catalog(session)
    for item in catalog["items"]:
        if item.get("kind") == "item" and int(item.get("type_id") or 0) == type_id:
            return item
    return None
