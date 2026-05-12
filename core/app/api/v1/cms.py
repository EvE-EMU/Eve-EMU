"""CMS-style content for eve-emu (pages, announcements) — persistence TBD."""

from fastapi import APIRouter

router = APIRouter(prefix="/cms", tags=["CMS"])


@router.get("/pages")
async def list_pages() -> dict[str, list]:
    return {"items": []}
