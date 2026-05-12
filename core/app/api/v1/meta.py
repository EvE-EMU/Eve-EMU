from fastapi import APIRouter

from app.config import settings

router = APIRouter(tags=["Meta"])


@router.get("/meta")
async def meta() -> dict[str, str | bool]:
    return {
        "service": "eve-emu-core",
        "public_base_url": settings.public_base_url,
        "database_configured": bool(settings.database_url),
        "openapi_docs_enabled": settings.openapi_docs_enabled,
    }
