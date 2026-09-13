"""Wormhole chain mapping models (Innominat / Pathfinder style)."""

from __future__ import annotations

from datetime import datetime

from sqlalchemy import BigInteger, Boolean, DateTime, ForeignKey, Integer, String, Text, func
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base


class WormholeMap(Base):
    __tablename__ = "emums_wh_maps"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    name: Mapped[str] = mapped_column(String(128))
    creator_character_id: Mapped[int] = mapped_column(BigInteger, index=True)
    creator_character_name: Mapped[str] = mapped_column(String(128), default="")
    alliance_id: Mapped[int | None] = mapped_column(BigInteger, nullable=True, index=True)
    active_tracking_character_id: Mapped[int | None] = mapped_column(BigInteger, nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )


class WormholeSystem(Base):
    __tablename__ = "emums_wh_systems"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    map_id: Mapped[int] = mapped_column(ForeignKey("emums_wh_maps.id"), index=True)
    solar_system_id: Mapped[int] = mapped_column(Integer, index=True)
    system_name: Mapped[str] = mapped_column(String(128), default="")
    system_signature: Mapped[str] = mapped_column(String(32), default="", index=True)
    wh_class: Mapped[str] = mapped_column(String(16), default="")  # C1–C6, C13, etc.
    space_type: Mapped[str] = mapped_column(String(16), default="j-space")  # j-space|k-space
    effect: Mapped[str] = mapped_column(String(64), default="")
    statics_json: Mapped[str] = mapped_column(Text, default="[]")
    pos_x: Mapped[float] = mapped_column(default=0.0)
    pos_y: Mapped[float] = mapped_column(default=0.0)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )


class WormholeConnection(Base):
    MASS_NORMAL = "normal"
    MASS_REDUCED = "reduced"
    MASS_CRITICAL = "critical"

    __tablename__ = "emums_wh_connections"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    map_id: Mapped[int] = mapped_column(ForeignKey("emums_wh_maps.id"), index=True)
    source_node_id: Mapped[int] = mapped_column(ForeignKey("emums_wh_systems.id"), index=True)
    target_node_id: Mapped[int] = mapped_column(ForeignKey("emums_wh_systems.id"), index=True)
    wh_type: Mapped[str] = mapped_column(String(32), default="")
    mass_status: Mapped[str] = mapped_column(String(16), default=MASS_NORMAL)
    eol: Mapped[bool] = mapped_column(Boolean, default=False)
    signature_in: Mapped[str] = mapped_column(String(32), default="")
    signature_out: Mapped[str] = mapped_column(String(32), default="")
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )
