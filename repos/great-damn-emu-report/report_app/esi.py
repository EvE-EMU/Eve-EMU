"""ESI access via a registered AA forwarder link."""

from __future__ import annotations

import sys
from pathlib import Path
from typing import Any

_FORWARDER_ROOT = Path(__file__).resolve().parents[2] / "aa-esi-forwarder"
if _FORWARDER_ROOT.is_dir() and str(_FORWARDER_ROOT.resolve()) not in sys.path:
    sys.path.insert(0, str(_FORWARDER_ROOT.resolve()))

from esi_forwarder_client import EsiForwarderClient  # noqa: E402

from report_app.connections import AaLink, get_link


def client_for(link: AaLink) -> EsiForwarderClient:
    return EsiForwarderClient(
        user_agent="GreatDamnEMUReport/1.0",
        **link.client_kwargs(),
    )


def esi_get(
    link_id: str,
    path: str,
    *,
    params: dict[str, Any] | None = None,
    token_id: int | None = None,
) -> tuple[int, Any, dict[str, str]]:
    link = get_link(link_id)
    if link is None:
        raise KeyError(f"unknown or disabled link: {link_id}")
    tid = token_id if token_id is not None else (link.default_token_id or None)
    return client_for(link).esi_get(path, params=params, token_id=tid)


def test_link(link: AaLink) -> dict[str, Any]:
    return client_for(link).ping()
