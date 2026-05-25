"""Optional aa-structures bootstrap (env-gated)."""

from __future__ import annotations

import os


def maybe_bootstrap_structure_owners() -> None:
    if os.environ.get("AA_ENSURE_STRUCTURE_OWNER", "1").strip().lower() not in (
        "1",
        "true",
        "yes",
        "on",
    ):
        return
    from structures_corp_token import ensure_structure_owners_from_overrides

    ensure_structure_owners_from_overrides()

    from structures_hr_webhook import maybe_sync_structures_hr_webhook

    maybe_sync_structures_hr_webhook()
