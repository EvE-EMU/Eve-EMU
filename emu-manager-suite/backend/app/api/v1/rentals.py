"""Moon rental program API — inventory, applications, bills, ACL, automation."""

from __future__ import annotations

from decimal import Decimal

from fastapi import APIRouter, Depends, Header, HTTPException, Query
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.auth.deps import require_api_key
from app.db.session import get_db
from app.models.rentals import (
    MoonLease,
    RentalAclGrant,
    RentalApplication,
    RentalBill,
    RentalProgramSettings,
    RentableMoon,
)
from app.schemas.rentals import (
    MoonLeaseOut,
    RentalAclCreate,
    RentalAclOut,
    RentalApplicationCreate,
    RentalApplicationOut,
    RentalApplicationReview,
    RentalBillOut,
    RentalJobsResult,
    RentalSettingsOut,
    RentalSettingsUpdate,
    RentableMoonCreate,
    RentableMoonOut,
    RentableMoonUpdate,
)
from app.services.rental_acl import require_rental_admin
from app.services.rental_program import (
    apply_bill_payment,
    approve_application,
    load_rental_settings,
    reject_application,
    run_rental_jobs,
)

router = APIRouter(prefix="/rentals", tags=["Rentals"], dependencies=[Depends(require_api_key)])


def _character_id(header: str | None) -> int | None:
    if not header:
        return None
    try:
        return int(header.strip())
    except ValueError:
        return None


@router.get("/settings", response_model=RentalSettingsOut)
async def get_settings(db: AsyncSession = Depends(get_db)) -> RentalProgramSettings:
    return await load_rental_settings(db)


@router.patch("/settings", response_model=RentalSettingsOut)
async def update_settings(
    body: RentalSettingsUpdate,
    db: AsyncSession = Depends(get_db),
    x_emums_character_id: str | None = Header(default=None, alias="X-EMUMS-Character-Id"),
) -> RentalProgramSettings:
    try:
        await require_rental_admin(db, character_id=_character_id(x_emums_character_id))
    except PermissionError as exc:
        raise HTTPException(status_code=403, detail=str(exc)) from exc
    row = await load_rental_settings(db)
    for field, value in body.model_dump(exclude_unset=True).items():
        setattr(row, field, value)
    await db.commit()
    return row


@router.get("/moons", response_model=list[RentableMoonOut])
async def list_moons(
    db: AsyncSession = Depends(get_db),
    status: str | None = None,
) -> list[RentableMoon]:
    q = select(RentableMoon).order_by(RentableMoon.structure_name)
    if status:
        q = q.where(RentableMoon.status == status)
    return list((await db.scalars(q)).all())


@router.post("/moons", response_model=RentableMoonOut)
async def create_moon(
    body: RentableMoonCreate,
    db: AsyncSession = Depends(get_db),
    x_emums_character_id: str | None = Header(default=None, alias="X-EMUMS-Character-Id"),
) -> RentableMoon:
    try:
        await require_rental_admin(db, character_id=_character_id(x_emums_character_id))
    except PermissionError as exc:
        raise HTTPException(status_code=403, detail=str(exc)) from exc
    moon = RentableMoon(**body.model_dump())
    db.add(moon)
    await db.commit()
    return moon


@router.patch("/moons/{moon_id}", response_model=RentableMoonOut)
async def update_moon(
    moon_id: int,
    body: RentableMoonUpdate,
    db: AsyncSession = Depends(get_db),
    x_emums_character_id: str | None = Header(default=None, alias="X-EMUMS-Character-Id"),
) -> RentableMoon:
    try:
        await require_rental_admin(db, character_id=_character_id(x_emums_character_id))
    except PermissionError as exc:
        raise HTTPException(status_code=403, detail=str(exc)) from exc
    moon = await db.get(RentableMoon, moon_id)
    if not moon:
        raise HTTPException(status_code=404, detail="Moon not found")
    for field, value in body.model_dump(exclude_unset=True).items():
        setattr(moon, field, value)
    await db.commit()
    return moon


@router.get("/applications", response_model=list[RentalApplicationOut])
async def list_applications(
    db: AsyncSession = Depends(get_db),
    status: str | None = Query(default=None),
) -> list[RentalApplication]:
    q = select(RentalApplication).order_by(RentalApplication.created_at.desc())
    if status:
        q = q.where(RentalApplication.status == status)
    return list((await db.scalars(q)).all())


@router.post("/applications", response_model=RentalApplicationOut)
async def create_application(
    body: RentalApplicationCreate,
    db: AsyncSession = Depends(get_db),
) -> RentalApplication:
    moon = await db.get(RentableMoon, body.moon_id)
    if not moon or moon.status != "available":
        raise HTTPException(status_code=400, detail="Moon is not available")
    app = RentalApplication(**body.model_dump())
    db.add(app)
    await db.flush()
    cfg = await load_rental_settings(db)
    if cfg.auto_approve_applications:
        await approve_application(
            db,
            app,
            reviewer_character_id=0,
            reviewer_character_name="system",
            notes="Auto-approved",
        )
    await db.commit()
    return app


@router.post("/applications/{application_id}/approve", response_model=MoonLeaseOut)
async def approve_rental_application(
    application_id: int,
    body: RentalApplicationReview,
    db: AsyncSession = Depends(get_db),
    x_emums_character_id: str | None = Header(default=None, alias="X-EMUMS-Character-Id"),
) -> MoonLease:
    try:
        await require_rental_admin(
            db,
            character_id=_character_id(x_emums_character_id) or body.reviewer_character_id,
        )
    except PermissionError as exc:
        raise HTTPException(status_code=403, detail=str(exc)) from exc
    app = await db.get(RentalApplication, application_id)
    if not app:
        raise HTTPException(status_code=404, detail="Application not found")
    try:
        lease = await approve_application(
            db,
            app,
            reviewer_character_id=body.reviewer_character_id,
            reviewer_character_name=body.reviewer_character_name,
            notes=body.notes,
        )
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    await db.commit()
    return lease


@router.post("/applications/{application_id}/reject", response_model=RentalApplicationOut)
async def reject_rental_application(
    application_id: int,
    body: RentalApplicationReview,
    db: AsyncSession = Depends(get_db),
    x_emums_character_id: str | None = Header(default=None, alias="X-EMUMS-Character-Id"),
) -> RentalApplication:
    try:
        await require_rental_admin(
            db,
            character_id=_character_id(x_emums_character_id) or body.reviewer_character_id,
        )
    except PermissionError as exc:
        raise HTTPException(status_code=403, detail=str(exc)) from exc
    app = await db.get(RentalApplication, application_id)
    if not app:
        raise HTTPException(status_code=404, detail="Application not found")
    try:
        await reject_application(
            app,
            reviewer_character_id=body.reviewer_character_id,
            reviewer_character_name=body.reviewer_character_name,
            notes=body.notes,
        )
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    await db.commit()
    return app


@router.get("/leases", response_model=list[MoonLeaseOut])
async def list_leases(
    db: AsyncSession = Depends(get_db),
    status: str | None = None,
    corporation_id: int | None = None,
) -> list[MoonLease]:
    q = select(MoonLease).order_by(MoonLease.started_at.desc())
    if status:
        q = q.where(MoonLease.status == status)
    if corporation_id:
        q = q.where(MoonLease.renter_corporation_id == corporation_id)
    return list((await db.scalars(q)).all())


@router.get("/bills", response_model=list[RentalBillOut])
async def list_bills(
    db: AsyncSession = Depends(get_db),
    status: str | None = None,
    lease_id: int | None = None,
) -> list[RentalBill]:
    q = select(RentalBill).order_by(RentalBill.due_at.desc())
    if status:
        q = q.where(RentalBill.status == status)
    if lease_id:
        q = q.where(RentalBill.lease_id == lease_id)
    return list((await db.scalars(q)).all())


@router.post("/bills/{bill_id}/confirm-paid", response_model=RentalBillOut)
async def confirm_bill_paid(
    bill_id: int,
    amount_isk: Decimal,
    db: AsyncSession = Depends(get_db),
    x_emums_character_id: str | None = Header(default=None, alias="X-EMUMS-Character-Id"),
) -> RentalBill:
    try:
        await require_rental_admin(db, character_id=_character_id(x_emums_character_id))
    except PermissionError as exc:
        raise HTTPException(status_code=403, detail=str(exc)) from exc
    bill = await db.get(RentalBill, bill_id)
    if not bill:
        raise HTTPException(status_code=404, detail="Bill not found")
    await apply_bill_payment(bill, amount_isk)
    await db.commit()
    return bill


@router.post("/bills/{bill_id}/void", response_model=RentalBillOut)
async def void_bill(
    bill_id: int,
    db: AsyncSession = Depends(get_db),
    x_emums_character_id: str | None = Header(default=None, alias="X-EMUMS-Character-Id"),
) -> RentalBill:
    try:
        await require_rental_admin(db, character_id=_character_id(x_emums_character_id))
    except PermissionError as exc:
        raise HTTPException(status_code=403, detail=str(exc)) from exc
    bill = await db.get(RentalBill, bill_id)
    if not bill:
        raise HTTPException(status_code=404, detail="Bill not found")
    bill.status = RentalBill.STATUS_VOID
    await db.commit()
    return bill


@router.get("/acl", response_model=list[RentalAclOut])
async def list_acl(db: AsyncSession = Depends(get_db)) -> list[RentalAclGrant]:
    return list((await db.scalars(select(RentalAclGrant).order_by(RentalAclGrant.id))).all())


@router.post("/acl", response_model=RentalAclOut)
async def create_acl(
    body: RentalAclCreate,
    db: AsyncSession = Depends(get_db),
    x_emums_character_id: str | None = Header(default=None, alias="X-EMUMS-Character-Id"),
) -> RentalAclGrant:
    try:
        await require_rental_admin(
            db,
            character_id=_character_id(x_emums_character_id),
            allow_bootstrap=True,
        )
    except PermissionError as exc:
        raise HTTPException(status_code=403, detail=str(exc)) from exc
    if not body.character_id and not body.corporation_id:
        raise HTTPException(status_code=400, detail="character_id or corporation_id required")
    if body.role not in (
        RentalAclGrant.ROLE_ADMIN,
        RentalAclGrant.ROLE_RENTER,
        RentalAclGrant.ROLE_VIEWER,
    ):
        raise HTTPException(status_code=400, detail="Invalid role")
    row = RentalAclGrant(**body.model_dump())
    db.add(row)
    await db.commit()
    return row


@router.delete("/acl/{grant_id}")
async def delete_acl(
    grant_id: int,
    db: AsyncSession = Depends(get_db),
    x_emums_character_id: str | None = Header(default=None, alias="X-EMUMS-Character-Id"),
) -> dict:
    try:
        await require_rental_admin(db, character_id=_character_id(x_emums_character_id))
    except PermissionError as exc:
        raise HTTPException(status_code=403, detail=str(exc)) from exc
    row = await db.get(RentalAclGrant, grant_id)
    if not row:
        raise HTTPException(status_code=404, detail="ACL grant not found")
    await db.delete(row)
    await db.commit()
    return {"deleted": grant_id}


@router.post("/jobs/run", response_model=RentalJobsResult)
async def run_jobs(db: AsyncSession = Depends(get_db)) -> RentalJobsResult:
    """Cron entry: generate bills, poll wallet, send reminders."""
    result = await run_rental_jobs(db)
    await db.commit()
    return RentalJobsResult(**result)


@router.post("/jobs/enqueue")
async def enqueue_rental_jobs() -> dict[str, str]:
    """Dispatch rental periodic jobs to Celery (non-blocking)."""
    from app.tasks.rentals import run_periodic_jobs

    task = run_periodic_jobs.delay()
    return {"task_id": task.id, "status": "queued"}
