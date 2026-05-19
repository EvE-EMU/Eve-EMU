"""Normalize EVE fleet MOTD / label HTML for substring matching."""

from __future__ import annotations

import re
from html import unescape

_TAG_RE = re.compile(r"<[^>]+>")
_WS_RE = re.compile(r"\s+")


def normalize_fleet_text(text: str) -> str:
    """Strip CCP-flavored HTML and collapse whitespace."""
    if not text:
        return ""
    plain = unescape(text)
    plain = _TAG_RE.sub(" ", plain)
    return _WS_RE.sub(" ", plain).strip()
