"""WH intel overlay — FastAPI entrypoint."""

from __future__ import annotations

import asyncio
import logging
from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles

from app.api.router import router as api_router
from app.config import settings
from app.db import SessionLocal, init_db
from app.services import intel_store, map_data, sov, wanderer_bridge

logger = logging.getLogger(__name__)
STATIC_DIR = Path(__file__).resolve().parent.parent / "static"


async def _background_sov_loop() -> None:
    while True:
        try:
            async with SessionLocal() as session:
                count = await sov.refresh_sov_tags(session)
                if wanderer_bridge.wanderer_sync_enabled():
                    tags = await intel_store.list_system_tags(session)
                    for sid, tag_rows in tags.items():
                        for row in tag_rows:
                            if row["source"] == "sov":
                                await wanderer_bridge.sync_sov_label(sid, row["tag"])
                logger.info("sov refresh tagged %s systems", count)
        except Exception:
            logger.exception("sov refresh failed")
        await asyncio.sleep(3600)


async def _background_wanderer_expire_loop() -> None:
    while True:
        try:
            async with SessionLocal() as session:
                cleared = await intel_store.prune_expired(session)
                for sid in cleared:
                    await wanderer_bridge.clear_intel_system(sid)
        except Exception:
            logger.exception("wanderer expire sync failed")
        await asyncio.sleep(30)


@asynccontextmanager
async def lifespan(app: FastAPI):
    await init_db()
    async with SessionLocal() as session:
        await map_data.ensure_map_data(session)
        await sov.refresh_sov_tags(session)
    task = asyncio.create_task(_background_sov_loop())
    expire_task = asyncio.create_task(_background_wanderer_expire_loop())
    yield
    expire_task.cancel()
    task.cancel()


app = FastAPI(title="WH Intel Overlay", lifespan=lifespan)
app.include_router(api_router)

if STATIC_DIR.is_dir():
    app.mount("/static", StaticFiles(directory=str(STATIC_DIR)), name="static")


@app.get("/health")
async def health():
    return {"ok": True}


@app.get("/")
async def index():
    index_path = STATIC_DIR / "index.html"
    if index_path.is_file():
        return FileResponse(index_path)
    return {"message": "WH intel overlay API", "docs": "/docs"}
