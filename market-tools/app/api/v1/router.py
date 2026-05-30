from fastapi import APIRouter

from app.api.v1 import (
    appraisal,
    browser,
    compare,
    contracts,
    health,
    hub_basket,
    margin,
    meta,
    pi,
    sync,
    volume,
)

api_v1 = APIRouter(prefix="/v1")

api_v1.include_router(health.router, tags=["health"])
api_v1.include_router(meta.router, tags=["meta"])
api_v1.include_router(margin.router, prefix="/margin", tags=["margin"])
api_v1.include_router(browser.router, prefix="/browser", tags=["browser"])
api_v1.include_router(compare.router, prefix="/compare", tags=["compare"])
api_v1.include_router(contracts.router, prefix="/contracts", tags=["contracts"])
api_v1.include_router(pi.router, prefix="/pi", tags=["pi"])
api_v1.include_router(volume.router, prefix="/volume", tags=["volume"])
api_v1.include_router(appraisal.router, prefix="/appraisal", tags=["appraisal"])
api_v1.include_router(hub_basket.router, prefix="/hub-basket", tags=["hub-basket"])
api_v1.include_router(sync.router, prefix="/sync", tags=["sync"])
