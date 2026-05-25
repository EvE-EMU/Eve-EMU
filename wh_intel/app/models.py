"""SQLAlchemy models for WH intel overlay."""

from __future__ import annotations

from datetime import datetime

from sqlalchemy import BigInteger, DateTime, Float, Index, String, Text, func
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column


class Base(DeclarativeBase):
    pass


class IntelPing(Base):
    """Parsed intel line → system activity ring."""

    __tablename__ = "intel_pings"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    channel: Mapped[str] = mapped_column(String(128), nullable=False, index=True)
    reported_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, index=True)
    solar_system_id: Mapped[int] = mapped_column(BigInteger, nullable=False, index=True)
    solar_system_name: Mapped[str] = mapped_column(String(256), nullable=False)
    raw_line: Mapped[str] = mapped_column(Text, nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )

    __table_args__ = (Index("ix_intel_pings_system_expires", "solar_system_id", "expires_at"),)


class IntelEntity(Base):
    """Characters / ships / structures mentioned on an intel ping."""

    __tablename__ = "intel_entities"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    ping_id: Mapped[int] = mapped_column(BigInteger, nullable=False, index=True)
    entity_type: Mapped[str] = mapped_column(String(32), nullable=False)
    entity_id: Mapped[int] = mapped_column(BigInteger, nullable=False, index=True)
    name: Mapped[str] = mapped_column(String(256), nullable=False)
    showinfo_type: Mapped[int | None] = mapped_column(BigInteger, nullable=True)
    portrait_url: Mapped[str | None] = mapped_column(String(512), nullable=True)


class GateBubble(Base):
    """Anchored bubble marker on a stargate link (this side / that side)."""

    __tablename__ = "gate_bubbles"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    from_system_id: Mapped[int] = mapped_column(BigInteger, nullable=False, index=True)
    to_system_id: Mapped[int] = mapped_column(BigInteger, nullable=False, index=True)
    # "from" = bubble on from_system side of gate; "to" = far side.
    side: Mapped[str] = mapped_column(String(8), nullable=False)
    note: Mapped[str] = mapped_column(String(512), nullable=False, default="")
    placed_by: Mapped[str] = mapped_column(String(128), nullable=False, default="")
    expires_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )


class SystemTag(Base):
    """Multiple tags per system (sov, manual, intel-derived)."""

    __tablename__ = "system_tags"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    solar_system_id: Mapped[int] = mapped_column(BigInteger, nullable=False, index=True)
    tag: Mapped[str] = mapped_column(String(128), nullable=False)
    source: Mapped[str] = mapped_column(String(32), nullable=False, default="manual")
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )

    __table_args__ = (
        Index("ix_system_tags_unique", "solar_system_id", "tag", "source", unique=True),
    )


class MapSystem(Base):
    """Cached system layout + metadata for map rendering."""

    __tablename__ = "map_systems"

    solar_system_id: Mapped[int] = mapped_column(BigInteger, primary_key=True)
    name: Mapped[str] = mapped_column(String(256), nullable=False, index=True)
    security: Mapped[float] = mapped_column(Float, nullable=False, default=0.0)
    region_id: Mapped[int | None] = mapped_column(BigInteger, nullable=True)
    x: Mapped[float] = mapped_column(Float, nullable=False, default=0.0)
    y: Mapped[float] = mapped_column(Float, nullable=False, default=0.0)


class ServiceMeta(Base):
    """Key/value flags (e.g. map graph bootstrap completed)."""

    __tablename__ = "service_meta"

    key: Mapped[str] = mapped_column(String(64), primary_key=True)
    value: Mapped[str] = mapped_column(String(256), nullable=False, default="")


class MapJump(Base):
    __tablename__ = "map_jumps"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    from_system_id: Mapped[int] = mapped_column(BigInteger, nullable=False, index=True)
    to_system_id: Mapped[int] = mapped_column(BigInteger, nullable=False, index=True)

    __table_args__ = (
        Index("ix_map_jumps_pair", "from_system_id", "to_system_id", unique=True),
    )
