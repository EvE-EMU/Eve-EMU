"""Coalition identity layer — states, groups, RBAC (Alliance Auth replacement)."""

from __future__ import annotations

from datetime import datetime

from sqlalchemy import BigInteger, Boolean, DateTime, ForeignKey, Integer, String, Text, func
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base


class EmumsState(Base):
    __tablename__ = "emums_states"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    name: Mapped[str] = mapped_column(String(64), unique=True, index=True)
    priority_weight: Mapped[int] = mapped_column(Integer, default=100, index=True)
    color: Mapped[str] = mapped_column(String(24), default="blue")
    description: Mapped[str] = mapped_column(Text, default="")
    active: Mapped[bool] = mapped_column(Boolean, default=True)


class EmumsStateRule(Base):
    __tablename__ = "emums_state_rules"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    state_id: Mapped[int] = mapped_column(ForeignKey("emums_states.id"), index=True)
    allowed_alliance_ids_json: Mapped[str] = mapped_column(Text, default="[]")
    allowed_corporation_ids_json: Mapped[str] = mapped_column(Text, default="[]")
    priority: Mapped[int] = mapped_column(Integer, default=100)


class EmumsGroup(Base):
    __tablename__ = "emums_groups"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    name: Mapped[str] = mapped_column(String(128), unique=True, index=True)
    description: Mapped[str] = mapped_column(Text, default="")
    is_hidden: Mapped[bool] = mapped_column(Boolean, default=False)
    is_open: Mapped[bool] = mapped_column(Boolean, default=False)
    discord_role_id: Mapped[str] = mapped_column(String(32), default="")
    permissions_json: Mapped[str] = mapped_column(Text, default="[]")
    active: Mapped[bool] = mapped_column(Boolean, default=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )


class EmumsCharacterGroupJoin(Base):
    STATUS_ACTIVE = "active"
    STATUS_PENDING = "pending"
    STATUS_REVOKED = "revoked"

    __tablename__ = "emums_character_group_joins"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    character_id: Mapped[int] = mapped_column(BigInteger, index=True)
    character_name: Mapped[str] = mapped_column(String(128), default="")
    group_id: Mapped[int] = mapped_column(ForeignKey("emums_groups.id"), index=True)
    status: Mapped[str] = mapped_column(String(16), default=STATUS_ACTIVE, index=True)
    granted_by_character_id: Mapped[int | None] = mapped_column(BigInteger, nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )
