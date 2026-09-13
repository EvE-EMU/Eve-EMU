"""Compare SDE types in the same inventory group."""

from __future__ import annotations

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import SdeTypeIndex
from app.services.sde_type_detail import get_type_detail


async def types_in_group(session: AsyncSession, group_name: str, *, limit: int = 40) -> list[dict]:
    if not group_name.strip():
        return []
    rows = (
        await session.scalars(
            select(SdeTypeIndex)
            .where(SdeTypeIndex.group_name == group_name.strip())
            .order_by(SdeTypeIndex.name)
            .limit(limit)
        )
    ).all()
    return [
        {
            "type_id": r.type_id,
            "name": r.name,
            "group_name": r.group_name,
            "category_name": r.category_name,
            "volume_m3": r.volume_m3,
            "base_price": float(r.base_price),
        }
        for r in rows
    ]


async def compare_types(session: AsyncSession, type_ids: list[int]) -> dict | None:
    ids = [int(x) for x in type_ids if int(x) > 0][:8]
    if len(ids) < 2:
        return None
    items: list[dict] = []
    attr_names: dict[int, str] = {}
    for tid in ids:
        detail = await get_type_detail(session, tid)
        if not detail:
            continue
        items.append(detail)
        for a in detail.get("attributes") or []:
            attr_names[int(a["attribute_id"])] = str(a["name"])

    if len(items) < 2:
        return None

    rows: list[dict] = []
    for aid, aname in sorted(attr_names.items(), key=lambda x: x[1].lower()):
        row: dict = {"attribute_id": aid, "name": aname, "values": {}}
        for item in items:
            val = next(
                (a["value"] for a in item.get("attributes") or [] if int(a["attribute_id"]) == aid),
                None,
            )
            row["values"][str(item["type_id"])] = val
        rows.append(row)

    req_rows: list[dict] = []
    all_req_names: set[str] = set()
    per_item_reqs: dict[str, list[dict]] = {}
    for item in items:
        reqs = item.get("requirements") or []
        per_item_reqs[str(item["type_id"])] = reqs
        for r in reqs:
            all_req_names.add(str(r.get("name") or ""))

    for rname in sorted(all_req_names):
        if not rname:
            continue
        row = {"name": rname, "levels": {}}
        for item in items:
            match = next((r for r in per_item_reqs[str(item["type_id"])] if r.get("name") == rname), None)
            row["levels"][str(item["type_id"])] = match.get("level") if match else None
        req_rows.append(row)

    return {
        "type_ids": [i["type_id"] for i in items],
        "items": [
            {
                "type_id": i["type_id"],
                "name": i["name"],
                "group_name": i.get("group_name") or "",
                "volume_m3": i.get("volume_m3") or 0,
                "base_price": i.get("base_price") or 0,
            }
            for i in items
        ],
        "attributes": rows,
        "requirements": req_rows,
    }
