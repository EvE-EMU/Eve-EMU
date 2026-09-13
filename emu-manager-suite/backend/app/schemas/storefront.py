"""Storefront API schemas."""

from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, Field


class StorefrontCartLineIn(BaseModel):
    key: str
    quantity: int = Field(..., ge=1)


class StorefrontOrderCreate(BaseModel):
    pickup_location_id: int | None = None
    lines: list[StorefrontCartLineIn]
    notes: str = ""


class StorefrontConfigPatch(BaseModel):
    enabled: bool | None = None
    corp_name: str | None = None
    corp_id: int | None = None
    inventory_character_ids: str | None = None
    corp_hangar_flag: str | None = None
    structure_id: int | None = None
    structure_name_contains: str | None = None
    system_name_contains: str | None = None
    price_hub: str | None = None
    discord_webhook_url: str | None = None
    staff_notify_character_id: int | None = None
    contract_expiration_hours: int | None = Field(default=None, ge=1, le=336)


class StorefrontLocationIn(BaseModel):
    label: str
    structure_name: str = ""
    structure_id: int = 0
    system_name: str = ""
    location_hint: str = ""
    is_default: bool = False
    active: bool = True
    sort_order: int = 0


class StorefrontLocationPatch(BaseModel):
    label: str | None = None
    structure_name: str | None = None
    structure_id: int | None = None
    system_name: str | None = None
    location_hint: str | None = None
    is_default: bool | None = None
    active: bool | None = None
    sort_order: int | None = None


class StorefrontOverrideIn(BaseModel):
    type_id: int
    type_name: str = ""
    price_override_isk: float | None = None
    fake_qty_add: int = 0
    hidden: bool = False
    note: str = ""


class StorefrontOverridePatch(BaseModel):
    type_name: str | None = None
    price_override_isk: float | None = None
    fake_qty_add: int | None = None
    hidden: bool | None = None
    note: str | None = None


class StorefrontKitItemIn(BaseModel):
    type_id: int
    type_name: str = ""
    quantity: int = Field(default=1, ge=1)


class StorefrontKitIn(BaseModel):
    name: str
    description: str = ""
    price_isk: float | None = None
    active: bool = True
    sort_order: int = 0
    items: list[StorefrontKitItemIn] = Field(default_factory=list)


class StorefrontKitPatch(BaseModel):
    name: str | None = None
    description: str | None = None
    price_isk: float | None = None
    active: bool | None = None
    sort_order: int | None = None
    items: list[StorefrontKitItemIn] | None = None


class StorefrontOrderStatusPatch(BaseModel):
    status: Literal["pending", "accepted", "fulfilled", "cancelled"]
