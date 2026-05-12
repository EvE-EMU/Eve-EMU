"""Build canonical URLs for ``images.evetech.net`` (Tranquility)."""

from __future__ import annotations

EVETECH_IMAGES_BASE = "https://images.evetech.net"


def type_icon_url(type_id: int, *, size: int = 64) -> str:
    """Inventory/type icon (PNG). Common sizes: 32, 64, 128, 256."""
    return f"{EVETECH_IMAGES_BASE}/types/{int(type_id)}/icon?size={size}"


def type_render_url(type_id: int, *, size: int = 256) -> str:
    """3D render (JPEG)."""
    return f"{EVETECH_IMAGES_BASE}/types/{int(type_id)}/render?size={size}"


def character_portrait_url(character_id: int, *, size: int = 256) -> str:
    """Character portrait; ``tenant=tranquility`` for TQ."""
    return (
        f"{EVETECH_IMAGES_BASE}/characters/{int(character_id)}/portrait"
        f"?tenant=tranquility&size={size}"
    )


def corporation_logo_url(corporation_id: int, *, size: int = 256) -> str:
    return (
        f"{EVETECH_IMAGES_BASE}/corporations/{int(corporation_id)}/logo"
        f"?tenant=tranquility&size={size}"
    )


def alliance_logo_url(alliance_id: int, *, size: int = 256) -> str:
    return (
        f"{EVETECH_IMAGES_BASE}/alliances/{int(alliance_id)}/logo"
        f"?tenant=tranquility&size={size}"
    )
