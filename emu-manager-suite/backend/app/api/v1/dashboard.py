"""Dashboard KPIs and chart series."""

from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from app.auth.deps import require_api_key
from app.db.session import get_db
from app.schemas import DashboardOut
from app.services.dashboard import build_dashboard

router = APIRouter(prefix="/dashboard", tags=["Dashboard"], dependencies=[Depends(require_api_key)])


@router.get("", response_model=DashboardOut)
async def get_dashboard(db: AsyncSession = Depends(get_db)) -> DashboardOut:
    return await build_dashboard(db)
