"""Pydantic models for bundled SRP matrix + doctrine JSON."""

from __future__ import annotations

from pydantic import BaseModel, Field
from pydantic import field_validator


class ToolLink(BaseModel):
    label: str = Field(..., min_length=1)
    href: str = Field(..., min_length=1)

    @field_validator("href")
    @classmethod
    def href_not_blank(cls, v: str) -> str:
        s = v.strip()
        if not s:
            raise ValueError("href must not be empty")
        return s


class SrpRow(BaseModel):
    category: str = Field(..., min_length=1)
    reimbursement: str = Field(..., min_length=1)
    cap_isk: int | None = Field(None, ge=0, description="Optional reimbursement cap in ISK")
    notes: str = ""


class SrpMatrix(BaseModel):
    title: str = "SRP matrix"
    last_updated: str = ""
    intro: str = ""
    rows: list[SrpRow] = Field(default_factory=list)
    links: list[ToolLink] = Field(default_factory=list)


class DoctrineHull(BaseModel):
    name: str = Field(..., min_length=1)
    count: int | None = Field(None, ge=1, description="Target hull count (optional)")
    note: str = ""
    fitting_link: str = ""


class DoctrineRole(BaseModel):
    role: str = Field(..., min_length=1)
    description: str = ""
    hulls: list[DoctrineHull] = Field(default_factory=list)


class DoctrineDoc(BaseModel):
    slug: str = Field(..., min_length=1, pattern=r"^[a-z0-9][a-z0-9-]*$")
    display_name: str = Field(..., min_length=1)
    summary: str = ""
    tags: list[str] = Field(default_factory=list)
    comms_note: str = ""
    fleet_roles: list[DoctrineRole] = Field(default_factory=list)
    pitfalls: list[str] = Field(default_factory=list)
    links: list[ToolLink] = Field(default_factory=list)


class DoctrineBundle(BaseModel):
    intro: str = ""
    doctrines: list[DoctrineDoc] = Field(default_factory=list)
