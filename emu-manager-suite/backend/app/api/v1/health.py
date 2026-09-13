"""Health and meta."""

from fastapi import APIRouter

from app import __version__
from app.config import settings
from app.schemas import HealthOut

router = APIRouter(tags=["Health"])


@router.get("/health", response_model=HealthOut)
async def health() -> HealthOut:
    return HealthOut(status="ok", version=__version__, environment=settings.environment)
