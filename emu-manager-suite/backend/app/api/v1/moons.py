"""Mining logs and invoices (EMU Moons domain fork)."""

from fastapi import APIRouter, Depends, Query
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.auth.deps import require_api_key
from app.db.session import get_db
from app.models import Invoice, MiningLog, StructureTaxRule
from app.schemas import InvoiceOut, MiningLogOut, StructureTaxRuleOut

router = APIRouter(prefix="/moons", tags=["Moons"], dependencies=[Depends(require_api_key)])


@router.get("/mining-logs", response_model=list[MiningLogOut])
async def list_mining_logs(
    db: AsyncSession = Depends(get_db),
    limit: int = Query(100, le=500),
    offset: int = 0,
) -> list[MiningLog]:
    result = await db.scalars(
        select(MiningLog).order_by(MiningLog.mined_date.desc()).offset(offset).limit(limit)
    )
    return list(result.all())


@router.get("/invoices", response_model=list[InvoiceOut])
async def list_invoices(
    db: AsyncSession = Depends(get_db),
    status: str | None = None,
    limit: int = Query(100, le=500),
) -> list[Invoice]:
    q = select(Invoice).order_by(Invoice.due_at.desc()).limit(limit)
    if status:
        q = q.where(Invoice.status == status)
    return list((await db.scalars(q)).all())


@router.get("/tax-rules", response_model=list[StructureTaxRuleOut])
async def list_tax_rules(db: AsyncSession = Depends(get_db)) -> list[StructureTaxRule]:
    rows = await db.scalars(
        select(StructureTaxRule).where(StructureTaxRule.active.is_(True)).order_by(
            StructureTaxRule.priority
        )
    )
    return list(rows.all())


@router.post("/invoices/generate")
async def enqueue_invoice_generation() -> dict[str, str]:
    """Dispatch moon tax invoice generation to the emu_moons Celery queue."""
    from app.tasks.emu_moons import generate_invoices

    task = generate_invoices.delay()
    return {"task_id": task.id, "status": "queued", "queue": "emu_moons"}
