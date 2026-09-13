"""FastAPI application entrypoint."""

from __future__ import annotations

import asyncio
import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.middleware.gzip import GZipMiddleware
from fastapi.responses import ORJSONResponse
from fastapi.staticfiles import StaticFiles

from app import __version__
from app.api.v1.router import api_v1
from app.config import settings
from app.db.init_schema import init_schema
from app.services.media_storage import backgrounds_dir

logger = logging.getLogger(__name__)


async def _refresh_structure_market_owners() -> None:
    try:
        from app.db.session import get_session_factory
        from app.services.structure_market_access import refresh_authed_structure_market_owners

        factory = get_session_factory()
        async with factory() as session:
            count = await refresh_authed_structure_market_owners(session)
            await session.commit()
        logger.info("EMUMS: refreshed structure market token owners (%s ok)", count)
    except Exception:
        logger.exception("EMUMS: structure market owner refresh failed")


@asynccontextmanager
async def lifespan(app: FastAPI):
    backgrounds_dir()
    await init_schema()
    if settings.environment == "production":
        insecure: list[str] = []
        if not settings.session_secret or settings.session_secret in {"emums-dev", "change-me"}:
            insecure.append("EMUMS_SESSION_SECRET")
        if settings.api_key in {"", "emums-dev-key-change-me"}:
            insecure.append("EMUMS_API_KEY")
        if settings.sso_client_id and not settings.sso_client_secret:
            insecure.append("EMUMS_SSO_CLIENT_SECRET")
        if insecure:
            logger.warning("EMUMS: insecure or missing secrets in production: %s", ", ".join(insecure))
    asyncio.create_task(_refresh_structure_market_owners())
    logger.info("EMUMS API ready at %s", settings.public_base_url)
    yield


def create_app() -> FastAPI:
    docs = "/docs" if settings.openapi_docs_enabled else None
    app = FastAPI(
        title=settings.app_name,
        description=(
            "Standalone EMU management ecosystem API. Forked from EMU Moons domain; "
            "no Alliance Auth. See /docs for OpenAPI."
        ),
        version=__version__,
        lifespan=lifespan,
        docs_url=docs,
        redoc_url="/redoc" if docs else None,
        default_response_class=ORJSONResponse,
    )
    app.add_middleware(GZipMiddleware, minimum_size=500)
    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.cors_origin_list,
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )
    app.include_router(api_v1, prefix=settings.api_prefix)
    media_mount = f"{settings.api_prefix.rstrip('/')}/media/backgrounds"
    app.mount(media_mount, StaticFiles(directory=str(backgrounds_dir())), name="background-media")
    return app


app = create_app()
