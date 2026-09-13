"""Persist uploaded desktop background videos."""

from __future__ import annotations

import re
import uuid
from pathlib import Path

from fastapi import HTTPException, UploadFile, status

from app.config import settings

ALLOWED_VIDEO_TYPES = {
    "video/mp4": ".mp4",
    "video/webm": ".webm",
    "video/quicktime": ".mov",
}

SAFE_LABEL = re.compile(r"[^a-zA-Z0-9._-]+")


def backgrounds_dir() -> Path:
    path = Path(settings.uploads_path) / "backgrounds"
    path.mkdir(parents=True, exist_ok=True)
    return path


def public_background_url(filename: str) -> str:
    base = settings.public_base_url.rstrip("/")
    prefix = settings.api_prefix.rstrip("/")
    return f"{base}{prefix}/media/backgrounds/{filename}"


def is_managed_upload_url(video_url: str) -> bool:
    marker = f"{settings.api_prefix.rstrip('/')}/media/backgrounds/"
    return marker in video_url


def filename_from_url(video_url: str) -> str | None:
    marker = f"{settings.api_prefix.rstrip('/')}/media/backgrounds/"
    if marker not in video_url:
        return None
    name = video_url.rsplit("/", 1)[-1]
    if not name or ".." in name or "/" in name:
        return None
    return name


async def save_background_video(file: UploadFile, label: str) -> tuple[str, str]:
    if not file.content_type or file.content_type not in ALLOWED_VIDEO_TYPES:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Unsupported video type. Use MP4, WebM, or MOV.",
        )

    raw = await file.read()
    if not raw:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Empty upload.")
    if len(raw) > settings.max_upload_bytes:
        raise HTTPException(
            status_code=status.HTTP_413_REQUEST_ENTITY_TOO_LARGE,
            detail=f"Video exceeds {settings.max_upload_mb} MB limit.",
        )

    slug = SAFE_LABEL.sub("-", label.strip().lower()).strip("-") or "background"
    ext = ALLOWED_VIDEO_TYPES[file.content_type]
    filename = f"{slug}-{uuid.uuid4().hex[:12]}{ext}"
    dest = backgrounds_dir() / filename
    dest.write_bytes(raw)
    return filename, public_background_url(filename)


def delete_background_file(video_url: str) -> None:
    filename = filename_from_url(video_url)
    if not filename:
        return
    path = backgrounds_dir() / filename
    if path.is_file():
        path.unlink(missing_ok=True)
