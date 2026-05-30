"""Registered Alliance Auth forwarder links (multi-tenant / external AA5)."""

from __future__ import annotations

import json
import re
from pathlib import Path
from typing import Any

from pydantic import BaseModel, Field

from report_app.config import settings

_SLUG = re.compile(r"^[a-z0-9][a-z0-9_-]{0,63}$")


class AaLink(BaseModel):
    """One remote AA5 instance (esi-forwarder + optional report-bridge)."""

    id: str = Field(..., description="Short slug, e.g. allied-bros")
    label: str = Field(..., description="Display name")
    forwarder_url: str = Field(..., description="Public AA base URL, e.g. https://auth.their-corp.com")
    secret: str = Field(..., description="API key (ESI forwarder + export API)")
    bridge_secret: str = Field(
        default="",
        description="Export API key if different from secret; empty = use secret",
    )
    webhook_secret: str = Field(
        default="",
        description="HMAC secret for POST /v1/ingest/{id}; empty = use secret",
    )
    default_token_id: int = 0
    enabled: bool = True

    def client_kwargs(self) -> dict[str, Any]:
        return {
            "base_url": self.forwarder_url.rstrip("/"),
            "secret": self.secret,
        }


class AaLinkPublic(BaseModel):
    id: str
    label: str
    forwarder_url: str
    default_token_id: int
    enabled: bool
    secret_hint: str


def _links_path() -> Path:
    return Path(settings.connections_file)


def _load_raw() -> list[dict[str, Any]]:
    path = _links_path()
    if path.is_file():
        data = json.loads(path.read_text(encoding="utf-8"))
        if isinstance(data, list):
            return data
    # Legacy single forwarder from env
    if settings.esi_forwarder_secret and settings.esi_forwarder_url:
        return [
            {
                "id": "default",
                "label": "Default (env)",
                "forwarder_url": settings.esi_forwarder_url,
                "secret": settings.esi_forwarder_secret,
                "default_token_id": settings.default_token_id,
                "enabled": True,
            }
        ]
    return []


def _save_raw(rows: list[dict[str, Any]]) -> None:
    path = _links_path()
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(rows, indent=2) + "\n", encoding="utf-8")


def list_links(*, include_disabled: bool = False) -> list[AaLink]:
    out: list[AaLink] = []
    for row in _load_raw():
        link = AaLink.model_validate(row)
        if include_disabled or link.enabled:
            out.append(link)
    return out


def get_link(link_id: str) -> AaLink | None:
    for link in list_links(include_disabled=True):
        if link.id == link_id and link.enabled:
            return link
    return None


def to_public(link: AaLink) -> AaLinkPublic:
    sec = link.secret
    hint = f"…{sec[-4:]}" if len(sec) >= 4 else "****"
    return AaLinkPublic(
        id=link.id,
        label=link.label,
        forwarder_url=link.forwarder_url,
        default_token_id=link.default_token_id,
        enabled=link.enabled,
        secret_hint=hint,
    )


def upsert_link(link: AaLink) -> AaLink:
    if not _SLUG.match(link.id):
        raise ValueError("id must be lowercase slug [a-z0-9_-]")
    rows = _load_raw()
    replaced = False
    for i, row in enumerate(rows):
        if row.get("id") == link.id:
            rows[i] = link.model_dump()
            replaced = True
            break
    if not replaced:
        rows.append(link.model_dump())
    _save_raw(rows)
    return link


def delete_link(link_id: str) -> bool:
    rows = _load_raw()
    new_rows = [r for r in rows if r.get("id") != link_id]
    if len(new_rows) == len(rows):
        return False
    _save_raw(new_rows)
    return True
