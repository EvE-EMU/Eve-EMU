"""Moon rental program — leases, bills, applications, ACL."""

from __future__ import annotations

from datetime import date, datetime
from decimal import Decimal

from sqlalchemy import BigInteger, Boolean, Date, DateTime, ForeignKey, Integer, String, Text, func
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base


class RentalProgramSettings(Base):
    """Singleton-style rental automation config."""

    __tablename__ = "emums_rental_settings"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    enabled: Mapped[bool] = mapped_column(Boolean, default=True)
    landlord_corporation_id: Mapped[int] = mapped_column(BigInteger, default=0)
    landlord_corporation_name: Mapped[str] = mapped_column(String(128), default="")
    wallet_division: Mapped[int] = mapped_column(Integer, default=7)
    payment_reference_prefix: Mapped[str] = mapped_column(String(32), default="RENT")
    due_grace_days: Mapped[int] = mapped_column(Integer, default=7)
    reminder_days_json: Mapped[str] = mapped_column(Text, default="[3,7,14,21]")
    wallet_poll_character_id: Mapped[int | None] = mapped_column(BigInteger, nullable=True)
    auto_approve_applications: Mapped[bool] = mapped_column(Boolean, default=False)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )


class RentableMoon(Base):
    __tablename__ = "emums_rentable_moons"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    structure_id: Mapped[int] = mapped_column(BigInteger, unique=True, index=True)
    structure_name: Mapped[str] = mapped_column(String(256), index=True)
    system_name: Mapped[str] = mapped_column(String(128), default="")
    moon_rarity: Mapped[str] = mapped_column(String(8), default="r16")
    monthly_rent_isk: Mapped[Decimal] = mapped_column(default=Decimal("0"))
    status: Mapped[str] = mapped_column(String(16), default="available", index=True)
    notes: Mapped[str] = mapped_column(Text, default="")
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )


class RentalApplication(Base):
    STATUS_PENDING = "pending"
    STATUS_APPROVED = "approved"
    STATUS_REJECTED = "rejected"
    STATUS_WITHDRAWN = "withdrawn"

    __tablename__ = "emums_rental_applications"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    moon_id: Mapped[int] = mapped_column(ForeignKey("emums_rentable_moons.id"), index=True)
    applicant_character_id: Mapped[int] = mapped_column(BigInteger, index=True)
    applicant_character_name: Mapped[str] = mapped_column(String(128))
    renter_corporation_id: Mapped[int] = mapped_column(BigInteger, index=True)
    renter_corporation_name: Mapped[str] = mapped_column(String(128), default="")
    monthly_rent_offered_isk: Mapped[Decimal] = mapped_column(default=Decimal("0"))
    duration_days: Mapped[int] = mapped_column(Integer, default=30)
    status: Mapped[str] = mapped_column(String(16), default=STATUS_PENDING, index=True)
    notes: Mapped[str] = mapped_column(Text, default="")
    reviewed_by_character_id: Mapped[int | None] = mapped_column(BigInteger, nullable=True)
    reviewed_by_character_name: Mapped[str] = mapped_column(String(128), default="")
    reviewed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), index=True
    )


class MoonLease(Base):
    STATUS_PENDING = "pending"
    STATUS_ACTIVE = "active"
    STATUS_EXPIRED = "expired"
    STATUS_REVOKED = "revoked"

    __tablename__ = "emums_moon_leases"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    moon_id: Mapped[int] = mapped_column(ForeignKey("emums_rentable_moons.id"), index=True)
    application_id: Mapped[int | None] = mapped_column(
        ForeignKey("emums_rental_applications.id"), nullable=True
    )
    renter_corporation_id: Mapped[int] = mapped_column(BigInteger, index=True)
    renter_corporation_name: Mapped[str] = mapped_column(String(128), default="")
    contact_character_id: Mapped[int | None] = mapped_column(BigInteger, nullable=True)
    contact_character_name: Mapped[str] = mapped_column(String(128), default="")
    started_at: Mapped[date] = mapped_column(Date)
    ends_at: Mapped[date | None] = mapped_column(Date, nullable=True)
    monthly_rent_isk: Mapped[Decimal] = mapped_column(default=Decimal("0"))
    status: Mapped[str] = mapped_column(String(16), default=STATUS_ACTIVE, index=True)
    notes: Mapped[str] = mapped_column(Text, default="")
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )


class RentalBill(Base):
    STATUS_OPEN = "open"
    STATUS_PARTIAL = "partial"
    STATUS_PAID = "paid"
    STATUS_OVERDUE = "overdue"
    STATUS_VOID = "void"

    __tablename__ = "emums_rental_bills"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    lease_id: Mapped[int] = mapped_column(ForeignKey("emums_moon_leases.id"), index=True)
    bill_number: Mapped[str] = mapped_column(String(32), unique=True, index=True)
    period_start: Mapped[date] = mapped_column(Date)
    period_end: Mapped[date] = mapped_column(Date)
    amount_due_isk: Mapped[Decimal] = mapped_column(default=Decimal("0"))
    amount_paid_isk: Mapped[Decimal] = mapped_column(default=Decimal("0"))
    status: Mapped[str] = mapped_column(String(16), default=STATUS_OPEN, index=True)
    due_at: Mapped[date] = mapped_column(Date, index=True)
    paid_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    wallet_transaction_id: Mapped[int | None] = mapped_column(BigInteger, nullable=True)
    reminders_sent_json: Mapped[str] = mapped_column(Text, default="{}")
    notes: Mapped[str] = mapped_column(Text, default="")
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )


class RentalAclGrant(Base):
    ROLE_ADMIN = "admin"
    ROLE_RENTER = "renter"
    ROLE_VIEWER = "viewer"

    __tablename__ = "emums_rental_acl"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    character_id: Mapped[int | None] = mapped_column(BigInteger, nullable=True, index=True)
    corporation_id: Mapped[int | None] = mapped_column(BigInteger, nullable=True, index=True)
    role: Mapped[str] = mapped_column(String(16), default=ROLE_VIEWER, index=True)
    notes: Mapped[str] = mapped_column(String(256), default="")
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )
