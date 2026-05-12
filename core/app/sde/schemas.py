"""Pydantic schemas for SDE HTTP responses."""

from __future__ import annotations

from pydantic import BaseModel, Field


class SdeTypeOut(BaseModel):
    type_id: int = Field(..., description="EVE type ID")
    group_id: int
    name: str
    published: bool
    volume: float | None = None
    mass: float | None = None
    portion_size: int | None = None
    description: str | None = None
    icon_url: str
    render_url: str


class SdeInvGroupOut(BaseModel):
    group_id: int
    category_id: int
    name: str


class SdeSolarSystemOut(BaseModel):
    solar_system_id: int
    name: str
    security: float
    constellation_id: int
    region_id: int


class SdeStatusOut(BaseModel):
    database_configured: bool
    types: int | None = None
    groups: int | None = None
    solar_systems: int | None = None
    detail: str | None = None
