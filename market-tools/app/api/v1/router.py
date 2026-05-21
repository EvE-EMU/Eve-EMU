from fastapi import APIRouter

from app.api.v1 import browser, health, margin, meta, sync

api_v1 = APIRouter(prefix="/v1")

api_v1.include_router(health.router, tags=["health"])
api_v1.include_router(meta.router, tags=["meta"])
api_v1.include_router(margin.router, prefix="/margin", tags=["margin"])
api_v1.include_router(browser.router, prefix="/browser", tags=["browser"])
api_v1.include_router(sync.router, prefix="/sync", tags=["sync"])
