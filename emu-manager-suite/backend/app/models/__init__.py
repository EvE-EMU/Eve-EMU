"""ORM models — forked/simplified from EMU Moons domain."""

from __future__ import annotations

from datetime import date, datetime
from decimal import Decimal

from sqlalchemy import BigInteger, Boolean, Date, DateTime, ForeignKey, Integer, String, Text, func
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base


class OrgSettings(Base):
    """Singleton-style org configuration (one row per deployment for now)."""

    __tablename__ = "emums_org_settings"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    org_name: Mapped[str] = mapped_column(String(128), default="EvE EMU | Edging Gone Wild")
    corporation_id: Mapped[int] = mapped_column(BigInteger, default=0)
    observer_corporation_id: Mapped[int] = mapped_column(BigInteger, default=0)
    tax_corp_name: Mapped[str] = mapped_column(String(128), default="")
    discord_webhook_url: Mapped[str] = mapped_column(String(512), default="")
    mail_enabled: Mapped[bool] = mapped_column(Boolean, default=False)
    mail_sender_character: Mapped[str] = mapped_column(String(128), default="")
    propaganda_tagline: Mapped[str] = mapped_column(
        String(256), default="MOON OUTPUT FOR THE WAR EFFORT"
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )


class StructureTaxRule(Base):
    __tablename__ = "emums_structure_tax_rules"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    pattern: Mapped[str] = mapped_column(String(256))
    priority: Mapped[int] = mapped_column(Integer, default=100)
    r16_pct: Mapped[Decimal] = mapped_column(default=Decimal("20"))
    r32_pct: Mapped[Decimal] = mapped_column(default=Decimal("30"))
    r64_pct: Mapped[Decimal] = mapped_column(default=Decimal("40"))
    active: Mapped[bool] = mapped_column(Boolean, default=True)
    notes: Mapped[str] = mapped_column(String(512), default="")


class MiningLog(Base):
    __tablename__ = "emums_mining_logs"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    mined_date: Mapped[date] = mapped_column(Date, index=True)
    structure_name: Mapped[str] = mapped_column(String(256), index=True)
    character_id: Mapped[int] = mapped_column(BigInteger, index=True)
    character_name: Mapped[str] = mapped_column(String(128))
    type_name: Mapped[str] = mapped_column(String(128))
    type_id: Mapped[int] = mapped_column(Integer)
    moon_rarity: Mapped[str] = mapped_column(String(8), default="r16")
    quantity: Mapped[int] = mapped_column(Integer)
    isk_value: Mapped[Decimal] = mapped_column(default=Decimal("0"))
    source: Mapped[str] = mapped_column(String(16), default="seed", index=True)
    system_id: Mapped[int | None] = mapped_column(Integer, nullable=True)


class Invoice(Base):
    __tablename__ = "emums_invoices"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    invoice_number: Mapped[str] = mapped_column(String(32), unique=True, index=True)
    character_name: Mapped[str] = mapped_column(String(128))
    corporation_name: Mapped[str] = mapped_column(String(128), default="")
    structure_name: Mapped[str] = mapped_column(String(256), default="")
    total_due_isk: Mapped[Decimal] = mapped_column(default=Decimal("0"))
    amount_paid_isk: Mapped[Decimal] = mapped_column(default=Decimal("0"))
    status: Mapped[str] = mapped_column(String(24), default="open", index=True)
    due_at: Mapped[date] = mapped_column(Date)
    on_naughty_list: Mapped[bool] = mapped_column(Boolean, default=False)


class MessageTemplate(Base):
    """DB-backed templates for mail, Discord, reports."""

    __tablename__ = "emums_message_templates"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    slug: Mapped[str] = mapped_column(String(64), unique=True, index=True)
    name: Mapped[str] = mapped_column(String(128))
    channel: Mapped[str] = mapped_column(String(32), default="mail")  # mail|discord|report|ui
    subject: Mapped[str] = mapped_column(String(256), default="")
    body: Mapped[str] = mapped_column(Text)
    variables_json: Mapped[str] = mapped_column(Text, default="[]")
    active: Mapped[bool] = mapped_column(Boolean, default=True)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )


class DesktopBackground(Base):
    """Rotating desktop background videos (admin-managed)."""

    __tablename__ = "emums_desktop_backgrounds"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    label: Mapped[str] = mapped_column(String(128))
    video_url: Mapped[str] = mapped_column(String(1024))
    active: Mapped[bool] = mapped_column(Boolean, default=True)
    sort_order: Mapped[int] = mapped_column(Integer, default=0)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )


class SystemNotification(Base):
    """Extensible in-app notifications (addons register plugin + type)."""

    __tablename__ = "emums_notifications"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    plugin: Mapped[str] = mapped_column(String(64), index=True)
    type: Mapped[str] = mapped_column(String(64), index=True)
    title: Mapped[str] = mapped_column(String(256))
    body: Mapped[str] = mapped_column(Text)
    payload_json: Mapped[str] = mapped_column(Text, default="{}")
    recipient_character_id: Mapped[int | None] = mapped_column(BigInteger, nullable=True, index=True)
    read: Mapped[bool] = mapped_column(Boolean, default=False, index=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), index=True
    )


class NotificationRead(Base):
    """Per-character read state for in-app notifications."""

    __tablename__ = "emums_notification_reads"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    notification_id: Mapped[int] = mapped_column(Integer, index=True)
    character_id: Mapped[int] = mapped_column(BigInteger, index=True)
    read_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )


from app.models.character_skills import CharacterSkillLevel
from app.models.tools import (  # noqa: F401, E402
    AppraisalReport,
    AuditProfile,
    BlueprintPublicContract,
    AuthedStructure,
    BuybackQuote,
    CorpMarketListing,
    CorpMarketOrder,
    FittingRecord,
    HrAccountFlag,
    HrBlacklistEntry,
    HrLeaveRequest,
    HrRoleTitle,
    CharacterCorpTitle,
    CharacterMarketOrder,
    IndustryCalcJob,
    IndustrialBuildStructure,
    IndustrialProject,
    IndyHubJob,
    IndyBlueprint,
    IndyCopyRequest,
    IndyJobRecord,
    KillboardLeaderboard,
    LinkedCharacter,
    MarketWatchItem,
    MarketHistoryDay,
    MaterialExchangeOrder,
    PniBill,
    PniStatement,
    ProjectJobCost,
    ProjectStockAssignment,
    RattingPayment,
    RattingTaxPeriod,
    RouteBookmark,
    SdeStargateLink,
    SdeSystem,
    SdeSystemActivityHour,
    SdeTypeIndex,
    ServiceLink,
    SrpLoss,
    SrpRateRule,
    StorefrontListing,
    SsoUser,
)
from app.models.storefront import (  # noqa: F401, E402
    StorefrontConfig,
    StorefrontItemOverride,
    StorefrontKit,
    StorefrontKitItem,
    StorefrontOrder,
    StorefrontPickupLocation,
)


class DashboardSnapshot(Base):
    """Cached chart series for fast dashboard loads."""

    __tablename__ = "emums_dashboard_snapshots"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    metric_key: Mapped[str] = mapped_column(String(64), unique=True, index=True)
    payload_json: Mapped[str] = mapped_column(Text)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )
