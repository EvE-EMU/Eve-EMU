"""Bulk EVE Ref reference data (tar.xz) — fast group + type catalog import."""

from __future__ import annotations

import io
import json
import logging
import tarfile
from typing import Any

import httpx

from app.db.models import MarketCatalogType, MarketGroup
from app.services.everef import localized_name

logger = logging.getLogger(__name__)

_ARCHIVE_URL = "https://data.everef.net/reference-data/reference-data-latest.tar.xz"
_UA = "EVE-EMU-Market/1.0 (+https://eve-emu.com; eve-ref)"


def download_reference_archive() -> bytes:
    with httpx.Client(timeout=300.0, follow_redirects=True) as client:
        resp = client.get(_ARCHIVE_URL, headers={"User-Agent": _UA})
    resp.raise_for_status()
    return resp.content


def _extract_json(archive: bytes, member: str) -> dict[str, Any]:
    with tarfile.open(fileobj=io.BytesIO(archive), mode="r:xz") as tf:
        extracted = tf.extractfile(member)
        if extracted is None:
            raise FileNotFoundError(f"{member} not in reference archive")
        return json.load(extracted)


def parse_market_groups(archive: bytes) -> list[MarketGroup]:
    raw = _extract_json(archive, "market_groups.json")
    rows: list[MarketGroup] = []
    for entry in raw.values():
        if not isinstance(entry, dict):
            continue
        try:
            gid = int(entry["market_group_id"])
        except (KeyError, TypeError, ValueError):
            continue
        parent = entry.get("parent_group_id")
        rows.append(
            MarketGroup(
                group_id=gid,
                name=localized_name(entry.get("name")) or f"Group {gid}",
                parent_group_id=int(parent) if parent is not None else None,
            )
        )
    return rows


def parse_catalog_types(archive: bytes) -> list[MarketCatalogType]:
    raw = _extract_json(archive, "types.json")
    rows: list[MarketCatalogType] = []
    for entry in raw.values():
        if not isinstance(entry, dict):
            continue
        if not entry.get("published", True):
            continue
        mg = entry.get("market_group_id")
        if mg is None:
            continue
        try:
            tid = int(entry["type_id"])
            gid = int(mg)
        except (KeyError, TypeError, ValueError):
            continue
        name = localized_name(entry.get("name")) or f"Type {tid}"
        rows.append(
            MarketCatalogType(
                type_id=tid,
                market_group_id=gid,
                name=name,
                name_lower=name.lower(),
            )
        )
    return rows
