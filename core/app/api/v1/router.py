from fastapi import APIRouter

from app.api.v1 import cms, discord_integration, health, media_public, meta, sde
from app.auth.eve_sso import router as eve_sso_router

api_v1 = APIRouter(prefix="/v1")

api_v1.include_router(health.router)
api_v1.include_router(meta.router)
api_v1.include_router(media_public.router)
api_v1.include_router(sde.router)
api_v1.include_router(cms.router)
api_v1.include_router(discord_integration.router)
api_v1.include_router(eve_sso_router)
