"""Static Data Export (SDE) tables — populated via ``scripts/import_sde_sqlite.py`` (Fuzzwork SQLite)."""

from __future__ import annotations

from sqlalchemy import BigInteger, Boolean, Float, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from app.db.models import Base


class SdeInvGroup(Base):
    """Inventory group (``invGroups`` in source SQLite)."""

    __tablename__ = "sde_inv_groups"

    group_id: Mapped[int] = mapped_column(BigInteger, primary_key=True)
    category_id: Mapped[int] = mapped_column(BigInteger, nullable=False, index=True)
    name: Mapped[str] = mapped_column(String(500), nullable=False)


class SdeType(Base):
    """Inventory type (``invTypes``)."""

    __tablename__ = "sde_types"

    type_id: Mapped[int] = mapped_column(BigInteger, primary_key=True)
    group_id: Mapped[int] = mapped_column(BigInteger, nullable=False, index=True)
    name: Mapped[str] = mapped_column(String(500), nullable=False, index=True)
    published: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True, index=True)
    volume: Mapped[float | None] = mapped_column(Float, nullable=True)
    mass: Mapped[float | None] = mapped_column(Float, nullable=True)
    portion_size: Mapped[int | None] = mapped_column(BigInteger, nullable=True)
    description: Mapped[str | None] = mapped_column(Text, nullable=True)


class SdeMapSolarSystem(Base):
    """Map solar system (``mapSolarSystems``)."""

    __tablename__ = "sde_map_solar_systems"

    solar_system_id: Mapped[int] = mapped_column(BigInteger, primary_key=True)
    name: Mapped[str] = mapped_column(String(256), nullable=False, index=True)
    security: Mapped[float] = mapped_column(Float, nullable=False, index=True)
    constellation_id: Mapped[int] = mapped_column(BigInteger, nullable=False, index=True)
    region_id: Mapped[int] = mapped_column(BigInteger, nullable=False, index=True)
