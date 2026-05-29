"""Append legacy ``ObjectNotFound`` / ``provider`` exports for AA 5.1+ community apps."""

from __future__ import annotations

import os
import pathlib

_ROOT = os.environ.get("ALLIANCEAUTH_ROOT", "/opt/allianceauth")
PROVIDERS = pathlib.Path(_ROOT) / "allianceauth" / "eveonline" / "providers.py"

COMPAT_BLOCK = '''

# --- eve-emu: legacy imports for killstats, ledger, and similar community apps ---
class ObjectNotFound(Exception):
    """Raised when an ESI entity cannot be resolved (pre-5.1 providers API)."""

    def __init__(self, obj_id, type_name):
        self.id = obj_id
        self.type = type_name

    def __str__(self) -> str:
        return f"{self.type} with ID {self.id} not found."


provider = open_api_provider
'''


def main() -> None:
    text = PROVIDERS.read_text(encoding="utf-8")
    if "class ObjectNotFound" in text and "provider = open_api_provider" in text:
        return
    if "class ObjectNotFound" in text:
        if "provider = open_api_provider" not in text:
            text = text.rstrip() + "\n\nprovider = open_api_provider\n"
    else:
        text = text.rstrip() + COMPAT_BLOCK
    PROVIDERS.write_text(text, encoding="utf-8")


if __name__ == "__main__":
    main()
