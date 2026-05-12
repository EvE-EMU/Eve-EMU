"""Minimal ASGI entrypoint — replace with SSO, DB, and pollers."""

from fastapi import FastAPI

from app.config import settings

app = FastAPI(
    title="EVE-EMU Fleet Tracker",
    description="ESI-backed fleet participation and killmail tracking (scaffold).",
    version="0.0.1",
)


@app.get("/healthz")
async def healthz() -> dict[str, str]:
    return {"status": "ok"}


@app.get("/meta")
async def meta() -> dict[str, str]:
    return {
        "public_base_url": settings.public_base_url,
        "esi_base_url": settings.esi_base_url,
    }
