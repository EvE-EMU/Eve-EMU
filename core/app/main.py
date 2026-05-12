"""EVE-EMU Core — OpenAPI hub, auth, SDE, CMS for plugins."""

from contextlib import asynccontextmanager

from fastapi import FastAPI

from app.api.v1.router import api_v1
from app.config import settings
from app.db import get_engine, init_schema


@asynccontextmanager
async def lifespan(_app: FastAPI):
    get_engine()
    await init_schema()
    yield


def create_app() -> FastAPI:
    docs = "/docs" if settings.openapi_docs_enabled else None
    redoc = "/redoc" if settings.openapi_docs_enabled else None
    app = FastAPI(
        title="EVE-EMU Core",
        description=(
            "Authentication, SDE, CMS, and shared utilities for eve-emu tools. "
            "Stable integration surface: **/v1/** and **/openapi.json**."
        ),
        version="0.1.0",
        lifespan=lifespan,
        docs_url=docs,
        redoc_url=redoc,
    )
    app.include_router(api_v1)
    return app


app = create_app()
