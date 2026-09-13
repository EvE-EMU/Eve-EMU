"""Onboarding tasks, achievements, and admission KPI ranking."""

from __future__ import annotations

from datetime import datetime

from sqlalchemy import BigInteger, Boolean, DateTime, Float, Integer, String, Text, UniqueConstraint, func
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base


class OnboardingTask(Base):
    __tablename__ = "emums_onboarding_tasks"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    slug: Mapped[str] = mapped_column(String(64), unique=True, index=True)
    title: Mapped[str] = mapped_column(String(128))
    description: Mapped[str] = mapped_column(Text, default="")
    category: Mapped[str] = mapped_column(String(32), default="setup")  # setup|tools|social|combat
    points: Mapped[int] = mapped_column(Integer, default=10)
    sort_order: Mapped[int] = mapped_column(Integer, default=0)
    window_id: Mapped[str] = mapped_column(String(64), default="")  # neocom window to open
    auto_check: Mapped[str] = mapped_column(String(64), default="")  # auto completion key
    active: Mapped[bool] = mapped_column(Boolean, default=True)


class OnboardingProgress(Base):
    __tablename__ = "emums_onboarding_progress"
    __table_args__ = (UniqueConstraint("character_id", "task_id", name="uq_onboarding_char_task"),)

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    character_id: Mapped[int] = mapped_column(BigInteger, index=True)
    character_name: Mapped[str] = mapped_column(String(128), default="")
    task_id: Mapped[int] = mapped_column(Integer, index=True)
    completed: Mapped[bool] = mapped_column(Boolean, default=False)
    completed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    notes: Mapped[str] = mapped_column(String(256), default="")


class AdmissionKpi(Base):
    __tablename__ = "emums_admission_kpis"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    slug: Mapped[str] = mapped_column(String(64), unique=True, index=True)
    label: Mapped[str] = mapped_column(String(128))
    description: Mapped[str] = mapped_column(Text, default="")
    weight: Mapped[float] = mapped_column(Float, default=1.0)
    metric_key: Mapped[str] = mapped_column(String(64))  # sp|kills|kd|scopes|onboarding|standings|assets
    min_value: Mapped[float] = mapped_column(Float, default=0.0)
    target_value: Mapped[float] = mapped_column(Float, default=100.0)
    active: Mapped[bool] = mapped_column(Boolean, default=True)
    sort_order: Mapped[int] = mapped_column(Integer, default=0)


class AdmissionConfig(Base):
    __tablename__ = "emums_admission_config"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    admit_threshold: Mapped[float] = mapped_column(Float, default=60.0)
    review_threshold: Mapped[float] = mapped_column(Float, default=40.0)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )


class CharacterStanding(Base):
    __tablename__ = "emums_character_standings"
    __table_args__ = (
        UniqueConstraint("character_id", "from_id", "from_type", name="uq_char_standing"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    character_id: Mapped[int] = mapped_column(BigInteger, index=True)
    from_id: Mapped[int] = mapped_column(BigInteger, index=True)
    from_type: Mapped[str] = mapped_column(String(16), default="character")  # character|corporation|alliance|faction
    from_name: Mapped[str] = mapped_column(String(128), default="")
    standing: Mapped[float] = mapped_column(Float, default=0.0)
    synced_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )
