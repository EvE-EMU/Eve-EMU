"""Role checks for moon rental admin / renter ACL."""

from __future__ import annotations

from sqlalchemy import or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.rentals import RentalAclGrant


async def rental_roles_for_actor(
    session: AsyncSession,
    *,
    character_id: int | None = None,
    corporation_id: int | None = None,
) -> set[str]:
    roles: set[str] = set()
    if character_id:
        rows = await session.scalars(
            select(RentalAclGrant).where(RentalAclGrant.character_id == character_id)
        )
        roles.update(r.role for r in rows.all())
    if corporation_id:
        rows = await session.scalars(
            select(RentalAclGrant).where(RentalAclGrant.corporation_id == corporation_id)
        )
        roles.update(r.role for r in rows.all())
    return roles


async def is_rental_admin(
    session: AsyncSession,
    *,
    character_id: int | None = None,
    corporation_id: int | None = None,
) -> bool:
    roles = await rental_roles_for_actor(
        session, character_id=character_id, corporation_id=corporation_id
    )
    return RentalAclGrant.ROLE_ADMIN in roles


async def require_rental_admin(
    session: AsyncSession,
    *,
    character_id: int | None,
    corporation_id: int | None = None,
    allow_bootstrap: bool = False,
) -> None:
    grants = await session.scalar(select(RentalAclGrant.id).limit(1))
    if allow_bootstrap and grants is None:
        return
    if not character_id:
        raise PermissionError("X-EMUMS-Character-Id required for rental admin actions")
    if not await is_rental_admin(
        session, character_id=character_id, corporation_id=corporation_id
    ):
        raise PermissionError("Rental admin ACL required")
