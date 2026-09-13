"""Default desktop background videos for new deployments."""

from __future__ import annotations

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import DesktopBackground

# Mixkit direct CDN format: /videos/{id}/{id}-720.mp4 (preview/* URLs return 403)
DEFAULT_DESKTOP_BACKGROUNDS = [
    {
        "label": "Deep space drift",
        "video_url": "https://assets.mixkit.co/videos/1610/1610-720.mp4",
        "sort_order": 0,
    },
    {
        "label": "Orbital moon",
        "video_url": "https://assets.mixkit.co/videos/31772/31772-720.mp4",
        "sort_order": 1,
    },
    {
        "label": "Nebula passage",
        "video_url": "https://assets.mixkit.co/videos/31532/31532-720.mp4",
        "sort_order": 2,
    },
    {
        "label": "Planet horizon",
        "video_url": "https://assets.mixkit.co/videos/4079/4079-720.mp4",
        "sort_order": 3,
    },
]

# Legacy broken preview URLs shipped in early builds
LEGACY_URL_FIXES: dict[str, str] = {
    "https://assets.mixkit.co/videos/preview/mixkit-stars-in-space-1610-large.mp4": DEFAULT_DESKTOP_BACKGROUNDS[0]["video_url"],
    "https://assets.mixkit.co/videos/preview/mixkit-rotating-moon-in-the-dark-universe-31772-large.mp4": DEFAULT_DESKTOP_BACKGROUNDS[1]["video_url"],
    "https://assets.mixkit.co/videos/preview/mixkit-flying-through-the-nebula-31532-large.mp4": DEFAULT_DESKTOP_BACKGROUNDS[2]["video_url"],
    "https://assets.mixkit.co/videos/preview/mixkit-earth-taking-a-full-rotation-4079-large.mp4": DEFAULT_DESKTOP_BACKGROUNDS[3]["video_url"],
}


async def ensure_default_desktop_backgrounds(session: AsyncSession) -> None:
    count = await session.scalar(select(func.count()).select_from(DesktopBackground))
    if count and count > 0:
        await repair_desktop_background_urls(session)
        return
    for item in DEFAULT_DESKTOP_BACKGROUNDS:
        session.add(DesktopBackground(**item, active=True))
    await session.flush()


async def repair_desktop_background_urls(session: AsyncSession) -> None:
    """Fix broken Mixkit preview URLs and ensure at least one active background."""
    rows = list((await session.scalars(select(DesktopBackground))).all())
    repaired_ids: list[int] = []

    for row in rows:
        fixed = LEGACY_URL_FIXES.get(row.video_url)
        if fixed:
            row.video_url = fixed
            row.active = True
            repaired_ids.append(row.id)
        elif "/videos/preview/" in row.video_url:
            row.active = False

    active_count = await session.scalar(
        select(func.count()).select_from(DesktopBackground).where(DesktopBackground.active.is_(True))
    )
    if (active_count or 0) == 0 and rows:
        for row in rows:
            if row.video_url in {d["video_url"] for d in DEFAULT_DESKTOP_BACKGROUNDS}:
                row.active = True

    await session.flush()
