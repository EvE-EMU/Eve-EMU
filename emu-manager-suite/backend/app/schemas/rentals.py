"""Pydantic I/O for moon rental program."""

from __future__ import annotations

from datetime import date, datetime
from decimal import Decimal

from pydantic import BaseModel, ConfigDict, Field


class RentalSettingsOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    enabled: bool
    landlord_corporation_id: int
    landlord_corporation_name: str
    wallet_division: int
    payment_reference_prefix: str
    due_grace_days: int
    reminder_days_json: str
    wallet_poll_character_id: int | None
    auto_approve_applications: bool
    updated_at: datetime


class RentalSettingsUpdate(BaseModel):
    enabled: bool | None = None
    landlord_corporation_id: int | None = None
    landlord_corporation_name: str | None = None
    wallet_division: int | None = None
    payment_reference_prefix: str | None = None
    due_grace_days: int | None = None
    reminder_days_json: str | None = None
    wallet_poll_character_id: int | None = None
    auto_approve_applications: bool | None = None


class RentableMoonOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    structure_id: int
    structure_name: str
    system_name: str
    moon_rarity: str
    monthly_rent_isk: Decimal
    status: str
    notes: str


class RentableMoonCreate(BaseModel):
    structure_id: int
    structure_name: str
    system_name: str = ""
    moon_rarity: str = "r16"
    monthly_rent_isk: Decimal = Decimal("0")
    status: str = "available"
    notes: str = ""


class RentableMoonUpdate(BaseModel):
    structure_name: str | None = None
    system_name: str | None = None
    moon_rarity: str | None = None
    monthly_rent_isk: Decimal | None = None
    status: str | None = None
    notes: str | None = None


class RentalApplicationOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    moon_id: int
    applicant_character_id: int
    applicant_character_name: str
    renter_corporation_id: int
    renter_corporation_name: str
    monthly_rent_offered_isk: Decimal
    duration_days: int
    status: str
    notes: str
    reviewed_by_character_name: str
    reviewed_at: datetime | None
    created_at: datetime


class RentalApplicationCreate(BaseModel):
    moon_id: int
    applicant_character_id: int
    applicant_character_name: str
    renter_corporation_id: int
    renter_corporation_name: str = ""
    monthly_rent_offered_isk: Decimal
    duration_days: int = Field(default=30, ge=14, le=365)
    notes: str = ""


class RentalApplicationReview(BaseModel):
    reviewer_character_id: int
    reviewer_character_name: str
    notes: str = ""


class MoonLeaseOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    moon_id: int
    application_id: int | None
    renter_corporation_id: int
    renter_corporation_name: str
    contact_character_name: str
    started_at: date
    ends_at: date | None
    monthly_rent_isk: Decimal
    status: str
    notes: str


class RentalBillOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    lease_id: int
    bill_number: str
    period_start: date
    period_end: date
    amount_due_isk: Decimal
    amount_paid_isk: Decimal
    status: str
    due_at: date
    paid_at: datetime | None
    wallet_transaction_id: int | None


class RentalAclOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    character_id: int | None
    corporation_id: int | None
    role: str
    notes: str


class RentalAclCreate(BaseModel):
    character_id: int | None = None
    corporation_id: int | None = None
    role: str = "viewer"
    notes: str = ""


class RentalJobsResult(BaseModel):
    bills_created: int
    bills_marked_overdue: int
    payments_matched: int
    reminders_sent: int
    applications_auto_approved: int
