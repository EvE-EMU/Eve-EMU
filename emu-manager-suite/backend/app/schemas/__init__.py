"""Pydantic request/response models."""

from __future__ import annotations

from datetime import date, datetime
from decimal import Decimal

from pydantic import BaseModel, ConfigDict, Field


class HealthOut(BaseModel):
    status: str
    version: str
    environment: str


class OrgSettingsOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    org_name: str
    corporation_id: int
    observer_corporation_id: int
    tax_corp_name: str
    discord_webhook_url: str
    mail_enabled: bool
    mail_sender_character: str
    propaganda_tagline: str


class OrgSettingsUpdate(BaseModel):
    org_name: str | None = None
    corporation_id: int | None = None
    observer_corporation_id: int | None = None
    tax_corp_name: str | None = None
    discord_webhook_url: str | None = None
    mail_enabled: bool | None = None
    mail_sender_character: str | None = None
    propaganda_tagline: str | None = None


class StructureTaxRuleOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    pattern: str
    priority: int
    r16_pct: Decimal
    r32_pct: Decimal
    r64_pct: Decimal
    active: bool
    notes: str


class MiningLogOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    mined_date: date
    structure_name: str
    character_name: str
    type_name: str
    moon_rarity: str
    quantity: int
    isk_value: Decimal


class InvoiceOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    invoice_number: str
    character_name: str
    corporation_name: str
    structure_name: str
    total_due_isk: Decimal
    amount_paid_isk: Decimal
    status: str
    due_at: date
    on_naughty_list: bool


class TemplateOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    slug: str
    name: str
    channel: str
    subject: str
    body: str
    variables_json: str
    active: bool
    updated_at: datetime


class TemplateCreate(BaseModel):
    slug: str = Field(min_length=2, max_length=64)
    name: str
    channel: str = "mail"
    subject: str = ""
    body: str
    variables_json: str = "[]"
    active: bool = True


class TemplateUpdate(BaseModel):
    name: str | None = None
    channel: str | None = None
    subject: str | None = None
    body: str | None = None
    variables_json: str | None = None
    active: bool | None = None


class TemplateRenderIn(BaseModel):
    variables: dict[str, str | int | float] = Field(default_factory=dict)


class TemplateRenderOut(BaseModel):
    subject: str
    body: str


class DashboardOut(BaseModel):
    tagline: str
    kpis: list[dict]
    mining_by_day: list[dict]
    rarity_mix: list[dict]
    top_structures: list[dict]
    invoice_status: list[dict]
    recent_invoices: list[InvoiceOut]


class DesktopBackgroundOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    label: str
    video_url: str
    active: bool
    sort_order: int
    created_at: datetime


class DesktopBackgroundCreate(BaseModel):
    label: str = Field(min_length=1, max_length=128)
    video_url: str = Field(min_length=8, max_length=1024)
    active: bool = True
    sort_order: int = 0


class DesktopBackgroundUpdate(BaseModel):
    label: str | None = Field(default=None, min_length=1, max_length=128)
    video_url: str | None = Field(default=None, min_length=8, max_length=1024)
    active: bool | None = None
    sort_order: int | None = None


class NotificationOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    plugin: str
    type: str
    title: str
    body: str
    payload_json: str
    recipient_character_id: int | None = None
    read: bool
    created_at: datetime


class NotificationCreate(BaseModel):
    plugin: str = Field(min_length=1, max_length=64)
    type: str = Field(min_length=1, max_length=64)
    title: str = Field(min_length=1, max_length=256)
    body: str
    payload_json: str = "{}"
    recipient_character_id: int | None = None


class NotificationMarkReadIn(BaseModel):
    ids: list[int] = Field(default_factory=list)
    all: bool = False
