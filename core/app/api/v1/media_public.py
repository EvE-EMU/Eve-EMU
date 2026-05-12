"""Plugin-friendly JSON for EVE Tech image URLs (no image proxying in core by default)."""

from fastapi import APIRouter, Query
from pydantic import BaseModel

from app.media.evetech import (
    alliance_logo_url,
    character_portrait_url,
    corporation_logo_url,
    type_icon_url,
    type_render_url,
)

router = APIRouter(prefix="/media", tags=["Media"])


class TypeImageUrls(BaseModel):
    type_id: int
    icon: str
    render: str


@router.get("/types/{type_id}/urls", response_model=TypeImageUrls)
async def type_image_urls(
    type_id: int,
    icon_size: int = Query(64, ge=32, le=256),
    render_size: int = Query(256, ge=64, le=2048),
) -> TypeImageUrls:
    return TypeImageUrls(
        type_id=type_id,
        icon=type_icon_url(type_id, size=icon_size),
        render=type_render_url(type_id, size=render_size),
    )


class CharacterPortraitUrls(BaseModel):
    character_id: int
    portrait: str


@router.get("/characters/{character_id}/portrait-url", response_model=CharacterPortraitUrls)
async def character_portrait(character_id: int, size: int = 256) -> CharacterPortraitUrls:
    return CharacterPortraitUrls(
        character_id=character_id,
        portrait=character_portrait_url(character_id, size=size),
    )


class CorporationLogoUrls(BaseModel):
    corporation_id: int
    logo: str


@router.get("/corporations/{corporation_id}/logo-url", response_model=CorporationLogoUrls)
async def corporation_logo(corporation_id: int, size: int = 256) -> CorporationLogoUrls:
    return CorporationLogoUrls(
        corporation_id=corporation_id,
        logo=corporation_logo_url(corporation_id, size=size),
    )


class AllianceLogoUrls(BaseModel):
    alliance_id: int
    logo: str


@router.get("/alliances/{alliance_id}/logo-url", response_model=AllianceLogoUrls)
async def alliance_logo(alliance_id: int, size: int = 256) -> AllianceLogoUrls:
    return AllianceLogoUrls(
        alliance_id=alliance_id,
        logo=alliance_logo_url(alliance_id, size=size),
    )
