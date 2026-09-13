"""Character trained skill levels (ESI sync + demo seed)."""

from __future__ import annotations

from sqlalchemy import BigInteger, Integer, String, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base


class CharacterSkillLevel(Base):
    __tablename__ = "emums_character_skill_levels"
    __table_args__ = (UniqueConstraint("character_id", "skill_type_id", name="uq_char_skill"),)

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    character_id: Mapped[int] = mapped_column(BigInteger, index=True)
    character_name: Mapped[str] = mapped_column(String(128), default="")
    skill_type_id: Mapped[int] = mapped_column(Integer, index=True)
    skill_name: Mapped[str] = mapped_column(String(128), default="")
    trained_level: Mapped[int] = mapped_column(Integer, default=0)
    skillpoints_in_skill: Mapped[int] = mapped_column(BigInteger, default=0)
