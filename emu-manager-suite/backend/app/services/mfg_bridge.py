"""Best-effort bridge: EMUMS industrial/storefront → core ManufacturingProject."""

from __future__ import annotations

import logging
import os
from typing import Any

import httpx

logger = logging.getLogger(__name__)


def _aa_base() -> str:
    return (
        os.environ.get("FREIGHT_AA_API_URL")
        or os.environ.get("AA_SITE_URL")
        or "https://auth.eve-emu.com"
    ).rstrip("/")


async def create_mfg_project_from_emums(
    *,
    hull_name: str,
    sale_price: float = 0,
    material_cost: float = 0,
    customer_character_name: str = "",
    source: str = "emums",
    materials: list[dict[str, Any]] | None = None,
    create_quote: bool = True,
    session_token: str | None = None,
) -> dict[str, Any]:
    """POST /public/mfg/projects via director session or MARKET_INTERNAL_SECRET."""
    secret = (
        os.environ.get("MARKET_INTERNAL_SECRET")
        or os.environ.get("AA_MARKET_INTERNAL_SECRET")
        or ""
    ).strip()
    if not session_token and not secret:
        return {
            "ok": False,
            "skipped": True,
            "reason": "no_mfg_session_or_secret",
            "note": "Set MARKET_INTERNAL_SECRET or pass director mfg session to bridge.",
        }
    payload: dict[str, Any] = {
        "hull_name": hull_name[:128],
        "sale_price": sale_price,
        "material_cost": material_cost,
        "status": "quote",
        "create_quote": create_quote,
        "customer_character_name": customer_character_name[:64],
        "source": source,
        "erp_materials": materials or [],
        "quote_lines": materials or [],
    }
    headers = {"Accept": "application/json", "Content-Type": "application/json"}
    if session_token:
        payload["session"] = session_token
        headers["X-Mfg-Session"] = session_token
    if secret:
        payload["internal_secret"] = secret
        headers["X-Internal-Secret"] = secret
    url = f"{_aa_base()}/public/mfg/projects"
    try:
        async with httpx.AsyncClient(timeout=20.0) as client:
            res = await client.post(url, json=payload, headers=headers)
            data = res.json() if res.content else {}
            if res.status_code >= 400:
                return {
                    "ok": False,
                    "skipped": False,
                    "error": data.get("error") or f"http_{res.status_code}",
                }
            code = (data.get("project") or {}).get("code")
            return {
                "ok": True,
                "code": code,
                "project": data.get("project"),
                "quote": data.get("quote"),
                "industrial_url": (
                    f"https://eve-emu.com/industrial/projects/{code}"
                    if code
                    else "https://eve-emu.com/industrial?tab=projects"
                ),
            }
    except Exception as exc:
        logger.warning("mfg bridge failed: %s", exc)
        return {"ok": False, "error": str(exc)}
