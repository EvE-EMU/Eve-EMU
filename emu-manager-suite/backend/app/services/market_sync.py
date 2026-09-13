"""Sync personal market orders from ESI."""

from __future__ import annotations

import logging
from datetime import UTC, datetime
from decimal import Decimal

from sqlalchemy import delete, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.tools import CharacterMarketOrder, SsoUser
from app.services.asset_labels import load_type_names
from app.services.audit_scopes import has_character_orders_access, parse_granted_scopes
from app.services.esi import bearer_token, esi_get_paged_list
from app.services.universe_locations import ensure_universe_locations

logger = logging.getLogger(__name__)

_ACTIVITY_RANGE = {
    "station": "Station",
    "region": "Region",
    "solarsystem": "System",
    "1": "1 jump",
    "2": "2 jumps",
    "3": "3 jumps",
    "4": "4 jumps",
    "5": "5 jumps",
    "10": "10 jumps",
    "20": "20 jumps",
    "30": "30 jumps",
    "40": "40 jumps",
}


async def sync_character_market_orders(
    session: AsyncSession,
    character_id: int,
    *,
    granted: set[str] | None = None,
    scope_errors: dict[str, str] | None = None,
) -> int:
    if granted is None:
        user = await session.scalar(select(SsoUser).where(SsoUser.character_id == character_id))
        granted = parse_granted_scopes(user.scopes_json if user else "")
    if not has_character_orders_access(granted):
        if scope_errors is not None:
            scope_errors["market_orders"] = "Missing scope: esi-markets.read_character_orders.v1"
        return 0

    token = await bearer_token(session, character_id=character_id)
    if not token:
        if scope_errors is not None:
            scope_errors["market_orders"] = "No valid SSO token — log in again."
        return 0

    user = await session.scalar(select(SsoUser).where(SsoUser.character_id == character_id))
    char_name = user.character_name if user else f"Character {character_id}"

    try:
        rows = await esi_get_paged_list(
            f"/characters/{character_id}/orders/",
            auth=True,
            session=session,
            character_id=character_id,
            max_pages=20,
        )
    except Exception:
        logger.exception("market orders sync failed for %s", character_id)
        return 0

    type_ids = {int(r.get("type_id") or 0) for r in rows if isinstance(r, dict)}
    location_ids = {int(r.get("location_id") or 0) for r in rows if isinstance(r, dict)}
    type_names = await load_type_names(session, {tid for tid in type_ids if tid > 0})
    loc_map = await ensure_universe_locations(session, list(location_ids), character_id=character_id)

    await session.execute(
        delete(CharacterMarketOrder).where(CharacterMarketOrder.character_id == character_id)
    )

    count = 0
    for row in rows:
        if not isinstance(row, dict):
            continue
        order_id = int(row.get("order_id") or 0)
        type_id = int(row.get("type_id") or 0)
        if not order_id or not type_id:
            continue
        loc_id = int(row.get("location_id") or 0)
        loc = loc_map.get(loc_id)
        loc_name = loc.name if loc else f"Location {loc_id}"
        rng = str(row.get("range") or "")
        session.add(
            CharacterMarketOrder(
                character_id=character_id,
                character_name=char_name[:128],
                order_id=order_id,
                type_id=type_id,
                type_name=type_names.get(type_id, f"Type {type_id}")[:256],
                is_buy_order=bool(row.get("is_buy_order")),
                price=Decimal(str(row.get("price") or 0)),
                volume_remain=int(row.get("volume_remain") or 0),
                volume_total=int(row.get("volume_total") or 0),
                min_volume=int(row.get("min_volume") or 0),
                location_id=loc_id,
                location_name=loc_name[:256],
                range_label=_ACTIVITY_RANGE.get(rng, rng)[:64],
                issued_at=_parse_ts(row.get("issued")),
                duration_days=int(row.get("duration") or 0),
                is_corporation=bool(row.get("is_corporation")),
            )
        )
        count += 1
    return count


def _parse_ts(value: str | None) -> datetime | None:
    if not value:
        return None
    try:
        return datetime.fromisoformat(str(value).replace("Z", "+00:00"))
    except (TypeError, ValueError):
        return None
