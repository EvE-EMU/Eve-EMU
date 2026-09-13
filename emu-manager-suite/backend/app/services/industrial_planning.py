"""Industrial Planning — build cost quotes, structure recommendation, true job costing."""

from __future__ import annotations

import secrets
from decimal import Decimal
from typing import Any

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import (
    FittingRecord,
    IndustrialBuildStructure,
    IndustrialProject,
    IndyBlueprint,
    ProjectJobCost,
    ProjectStockAssignment,
)


async def list_build_structures(
    session: AsyncSession,
    *,
    location_filter: str = "all",
    station_name: str | None = None,
) -> list[IndustrialBuildStructure]:
    rows = (
        await session.scalars(
            select(IndustrialBuildStructure)
            .where(IndustrialBuildStructure.has_manufacturing)
            .order_by(IndustrialBuildStructure.structure_name)
        )
    ).all()
    if location_filter == "stock":
        # Structures tagged as stock warehouses in DB (no hardcoded alliance names).
        rows = [
            r
            for r in rows
            if "stock" in (r.location_label or "").lower()
            or "warehouse" in (r.location_label or "").lower()
            or "stock" in (r.structure_name or "").lower()
            or "warehouse" in (r.structure_name or "").lower()
        ]
    elif location_filter == "station" and station_name:
        needle = station_name.strip().lower()
        rows = [
            r
            for r in rows
            if needle in r.structure_name.lower() or needle in r.location_label.lower()
        ]
    return rows


async def calculate_build_plan(
    session: AsyncSession,
    *,
    source_type: str,
    source_id: int,
    location_filter: str = "all",
    station_name: str | None = None,
    structure_id: int | None = None,
    runs: int = 1,
    viewer_character_id: int | None = None,
    material_mode: str = "base",
    price_hub: str = "jita",
    price_overrides: dict[int, Decimal] | None = None,
    stock_assignments: dict[int, int] | None = None,
    stock_location_ids: list[int] | None = None,
    use_max_stock: bool = True,
    project_id: int | None = None,
    container_name: str | None = None,
) -> dict[str, Any]:
    if viewer_character_id:
        from app.services.production_plan import calculate_production_plan

        return await calculate_production_plan(
            session,
            viewer_character_id=viewer_character_id,
            source_type=source_type,
            source_id=source_id,
            runs=runs,
            material_mode=material_mode,
            location_filter=location_filter,
            station_name=station_name,
            structure_id=structure_id,
            price_hub=price_hub,
            price_overrides=price_overrides,
            stock_assignments=stock_assignments,
            stock_location_ids=stock_location_ids,
            use_max_stock=use_max_stock,
            project_id=project_id,
            container_name=container_name,
        )

    structures = await list_build_structures(session, location_filter=location_filter, station_name=station_name)
    if not structures:
        return {"error": "no_structures"}
    return {
        "error": "auth_required",
        "message": "Log in to run a full production plan with SDE materials and stock.",
        "structures_available": [
            {"structure_id": s.structure_id, "structure_name": s.structure_name} for s in structures
        ],
    }


async def list_projects(session: AsyncSession) -> list[dict]:
    projects = (await session.scalars(select(IndustrialProject).order_by(IndustrialProject.id.desc()))).all()
    out = []
    for p in projects:
        stock = (
            await session.scalars(select(ProjectStockAssignment).where(ProjectStockAssignment.project_id == p.id))
        ).all()
        jobs = (await session.scalars(select(ProjectJobCost).where(ProjectJobCost.project_id == p.id))).all()
        mat_total = sum((s.unit_cost_isk * s.quantity for s in stock), Decimal("0"))
        job_total = sum((j.cost_isk for j in jobs), Decimal("0"))
        out.append(
            {
                "id": p.id,
                "project_code": p.project_code,
                "name": p.name,
                "container_name": p.container_name,
                "owner_character_name": p.owner_character_name,
                "status": p.status,
                "material_cost_isk": str(mat_total),
                "job_cost_isk": str(job_total),
                "true_cost_isk": str(mat_total + job_total),
                "notes": p.notes,
                "stock_lines": [
                    {
                        "type_name": s.type_name,
                        "quantity": s.quantity,
                        "unit_cost_isk": str(s.unit_cost_isk),
                        "container_name": s.container_name,
                    }
                    for s in stock
                ],
                "job_lines": [
                    {
                        "description": j.description,
                        "activity": j.activity,
                        "runs": j.runs,
                        "cost_isk": str(j.cost_isk),
                        "structure_name": j.structure_name,
                    }
                    for j in jobs
                ],
            }
        )
    return out


def new_project_code() -> str:
    return f"PROJ-{secrets.token_hex(2).upper()}"
