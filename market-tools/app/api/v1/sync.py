from fastapi import APIRouter

from app.sync.runner import schedule_structure_sync, structure_sync_running

router = APIRouter()


@router.get("/structure")
async def structure_sync_status() -> dict:
    return {"running": structure_sync_running()}


@router.post("/structure")
async def trigger_structure_sync() -> dict:
    """Pull WOMPSTAR market orders now (returns immediately; sync runs in background)."""
    return schedule_structure_sync()
