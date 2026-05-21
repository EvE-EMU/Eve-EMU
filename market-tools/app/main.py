"""EVE-EMU public market tools API."""

from __future__ import annotations

import asyncio
import logging
from contextlib import asynccontextmanager

from apscheduler.schedulers.asyncio import AsyncIOScheduler
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.api.v1.router import api_v1
from app.config import settings
from app.db.init_schema import init_schema
from app.db.session import get_engine
from app.sync.runner import run_structure_sync_job, schedule_structure_sync

logger = logging.getLogger(__name__)
_scheduler: AsyncIOScheduler | None = None


@asynccontextmanager
async def lifespan(app: FastAPI):
    global _scheduler
    get_engine()
    await init_schema()
    if settings.sync_enabled and settings.wompstar_structure_id:
        _scheduler = AsyncIOScheduler()
        _scheduler.add_job(
            run_structure_sync_job,
            "interval",
            minutes=max(5, settings.structure_orders_sync_interval_minutes),
            id="structure_orders",
            replace_existing=True,
        )
        _scheduler.start()
        # Do not block HTTP startup (group sync can take several minutes).
        asyncio.create_task(run_structure_sync_job())
    yield
    if _scheduler:
        _scheduler.shutdown(wait=False)


def create_app() -> FastAPI:
    docs = "/docs" if settings.openapi_docs_enabled else None
    app = FastAPI(
        title="EVE-EMU Market Tools",
        description="Public market browser, spreads, and WOMPSTAR data for eve-emu.com",
        version="0.1.0",
        lifespan=lifespan,
        docs_url=docs,
        redoc_url="/redoc" if docs else None,
    )
    app.add_middleware(
        CORSMiddleware,
        allow_origins=[settings.public_base_url, "http://localhost:8088"],
        allow_credentials=True,
        allow_methods=["GET", "POST", "OPTIONS"],
        allow_headers=["*"],
    )
    app.include_router(api_v1, prefix="/api/market")
    return app


app = create_app()
