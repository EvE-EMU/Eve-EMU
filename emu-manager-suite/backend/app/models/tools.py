"""ORM models for EMUMS coalition tool suite."""

from __future__ import annotations

from datetime import date, datetime
from decimal import Decimal

from sqlalchemy import BigInteger, Boolean, Date, DateTime, Float, Integer, Numeric, String, Text, func
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base


class SsoUser(Base):
    __tablename__ = "emums_sso_users"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    character_id: Mapped[int] = mapped_column(BigInteger, unique=True, index=True)
    character_name: Mapped[str] = mapped_column(String(128))
    corporation_id: Mapped[int] = mapped_column(BigInteger, default=0)
    corporation_name: Mapped[str] = mapped_column(String(128), default="")
    alliance_id: Mapped[int | None] = mapped_column(BigInteger, nullable=True)
    alliance_name: Mapped[str] = mapped_column(String(128), default="")
    access_token_enc: Mapped[str] = mapped_column(Text, default="")
    refresh_token_enc: Mapped[str] = mapped_column(Text, default="")
    scopes_json: Mapped[str] = mapped_column(Text, default="[]")
    last_login_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )


class LinkedCharacter(Base):
    __tablename__ = "emums_linked_characters"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    owner_user_id: Mapped[int] = mapped_column(Integer, index=True)
    character_id: Mapped[int] = mapped_column(BigInteger, index=True)
    character_name: Mapped[str] = mapped_column(String(128))
    corporation_id: Mapped[int] = mapped_column(BigInteger, default=0)
    is_main: Mapped[bool] = mapped_column(Boolean, default=False)
    token_valid: Mapped[bool] = mapped_column(Boolean, default=True)
    scopes_json: Mapped[str] = mapped_column(Text, default="[]")


class AuthedStructure(Base):
    """Structures with market or reprocessing available via linked character tokens."""

    __tablename__ = "emums_authed_structures"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    structure_id: Mapped[int] = mapped_column(BigInteger, unique=True, index=True)
    structure_name: Mapped[str] = mapped_column(String(256))
    system_name: Mapped[str] = mapped_column(String(128), default="")
    has_market: Mapped[bool] = mapped_column(Boolean, default=False)
    has_reprocessing: Mapped[bool] = mapped_column(Boolean, default=False)
    owner_character_id: Mapped[int] = mapped_column(BigInteger, default=0)
    solar_system_id: Mapped[int] = mapped_column(Integer, default=0)
    structure_type_id: Mapped[int] = mapped_column(Integer, default=0)
    structure_type_name: Mapped[str] = mapped_column(String(128), default="")
    structure_state: Mapped[str] = mapped_column(String(32), default="")
    fuel_expires_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    fuel_blocks_qty: Mapped[int] = mapped_column(Integer, default=0)
    corporation_id: Mapped[int] = mapped_column(BigInteger, default=0)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )


class AppraisalReport(Base):
    __tablename__ = "emums_appraisal_reports"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    share_token: Mapped[str] = mapped_column(String(32), unique=True, index=True)
    paste_text: Mapped[str] = mapped_column(Text)
    sell_market: Mapped[str] = mapped_column(String(32), default="jita")
    buy_market: Mapped[str] = mapped_column(String(32), default="jita")
    structure_id: Mapped[int | None] = mapped_column(BigInteger, nullable=True)
    result_json: Mapped[str] = mapped_column(Text, default="{}")
    created_by_character_id: Mapped[int | None] = mapped_column(BigInteger, nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), index=True
    )


class BuybackQuote(Base):
    __tablename__ = "emums_buyback_quotes"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    share_token: Mapped[str] = mapped_column(String(32), unique=True, index=True)
    paste_text: Mapped[str] = mapped_column(Text)
    fee_pct: Mapped[Decimal] = mapped_column(Numeric(8, 2), default=Decimal("90"))
    sell_market: Mapped[str] = mapped_column(String(32), default="jita")
    structure_id: Mapped[int | None] = mapped_column(BigInteger, nullable=True)
    contract_value_isk: Mapped[Decimal] = mapped_column(Numeric(20, 2), default=Decimal("0"))
    result_json: Mapped[str] = mapped_column(Text, default="{}")
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), index=True
    )


class SdeTypeIndex(Base):
    __tablename__ = "emums_sde_types"

    type_id: Mapped[int] = mapped_column(Integer, primary_key=True)
    name: Mapped[str] = mapped_column(String(256), index=True)
    group_name: Mapped[str] = mapped_column(String(128), default="")
    category_name: Mapped[str] = mapped_column(String(128), default="")
    volume_m3: Mapped[float] = mapped_column(Float, default=0)
    base_price: Mapped[Decimal] = mapped_column(Numeric(16, 4), default=Decimal("0"))


class AuditProfile(Base):
    __tablename__ = "emums_audit_profiles"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    character_id: Mapped[int] = mapped_column(BigInteger, unique=True, index=True)
    character_name: Mapped[str] = mapped_column(String(128))
    corporation_name: Mapped[str] = mapped_column(String(128), default="")
    wallet_balance_isk: Mapped[Decimal] = mapped_column(Numeric(20, 2), default=Decimal("0"))
    skill_points: Mapped[int] = mapped_column(BigInteger, default=0)
    assets_value_isk: Mapped[Decimal] = mapped_column(Numeric(20, 2), default=Decimal("0"))
    last_sync_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    snapshot_json: Mapped[str] = mapped_column(Text, default="{}")


class FittingRecord(Base):
    __tablename__ = "emums_fittings"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    name: Mapped[str] = mapped_column(String(256))
    ship_type_id: Mapped[int] = mapped_column(Integer, default=0)
    ship_type_name: Mapped[str] = mapped_column(String(128), default="")
    doctrine_slug: Mapped[str] = mapped_column(String(64), default="", index=True)
    eft_text: Mapped[str] = mapped_column(Text, default="")
    tags_json: Mapped[str] = mapped_column(Text, default="[]")
    public: Mapped[bool] = mapped_column(Boolean, default=True)
    owner_character_id: Mapped[int | None] = mapped_column(BigInteger, nullable=True, index=True)
    owner_character_name: Mapped[str] = mapped_column(String(128), default="")
    esi_fitting_id: Mapped[int | None] = mapped_column(BigInteger, nullable=True, unique=True, index=True)


class ServiceLink(Base):
    __tablename__ = "emums_service_links"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    service: Mapped[str] = mapped_column(String(32), index=True)  # discord|mumble|wiki
    label: Mapped[str] = mapped_column(String(128))
    url: Mapped[str] = mapped_column(String(512))
    description: Mapped[str] = mapped_column(String(512), default="")
    requires_sso: Mapped[bool] = mapped_column(Boolean, default=False)
    active: Mapped[bool] = mapped_column(Boolean, default=True)


class HrLeaveRequest(Base):
    __tablename__ = "emums_hr_leaves"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    character_name: Mapped[str] = mapped_column(String(128))
    character_id: Mapped[int] = mapped_column(BigInteger, default=0)
    start_date: Mapped[date] = mapped_column(Date)
    end_date: Mapped[date] = mapped_column(Date)
    reason: Mapped[str] = mapped_column(Text, default="")
    status: Mapped[str] = mapped_column(String(24), default="pending", index=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )


class HrBlacklistEntry(Base):
    __tablename__ = "emums_hr_blacklist"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    character_name: Mapped[str] = mapped_column(String(128), index=True)
    character_id: Mapped[int | None] = mapped_column(BigInteger, nullable=True)
    reason: Mapped[str] = mapped_column(Text, default="")
    added_by: Mapped[str] = mapped_column(String(128), default="")
    active: Mapped[bool] = mapped_column(Boolean, default=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )


class HrAccountFlag(Base):
    __tablename__ = "emums_hr_flags"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    target_character_id: Mapped[int] = mapped_column(BigInteger, index=True)
    target_character_name: Mapped[str] = mapped_column(String(128))
    flag_key: Mapped[str] = mapped_column(String(64), index=True)
    flag_label: Mapped[str] = mapped_column(String(128))
    color: Mapped[str] = mapped_column(String(24), default="warn")
    notes: Mapped[str] = mapped_column(Text, default="")
    active: Mapped[bool] = mapped_column(Boolean, default=True)


class HrRoleTitle(Base):
    """Corp titles that grant HR pilot lookup (configured in admin)."""

    __tablename__ = "emums_hr_role_titles"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    corporation_id: Mapped[int] = mapped_column(BigInteger, index=True)
    title_id: Mapped[int] = mapped_column(Integer, index=True)
    title_name: Mapped[str] = mapped_column(String(128))
    description: Mapped[str] = mapped_column(String(256), default="")
    active: Mapped[bool] = mapped_column(Boolean, default=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )


class CharacterCorpTitle(Base):
    """Cached ESI corporation title assignments per character."""

    __tablename__ = "emums_character_corp_titles"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    character_id: Mapped[int] = mapped_column(BigInteger, index=True)
    corporation_id: Mapped[int] = mapped_column(BigInteger, index=True)
    title_id: Mapped[int] = mapped_column(Integer, index=True)
    title_name: Mapped[str] = mapped_column(String(128))
    synced_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))


class RattingTaxPeriod(Base):
    __tablename__ = "emums_ratting_periods"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    period_label: Mapped[str] = mapped_column(String(64))
    rate_pct: Mapped[Decimal] = mapped_column(Numeric(8, 2), default=Decimal("10"))
    status: Mapped[str] = mapped_column(String(24), default="open")
    total_bounty_isk: Mapped[Decimal] = mapped_column(Numeric(20, 2), default=Decimal("0"))
    total_collected_isk: Mapped[Decimal] = mapped_column(Numeric(20, 2), default=Decimal("0"))


class RattingPayment(Base):
    __tablename__ = "emums_ratting_payments"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    period_id: Mapped[int] = mapped_column(Integer, index=True)
    character_name: Mapped[str] = mapped_column(String(128))
    bounty_isk: Mapped[Decimal] = mapped_column(Numeric(20, 2), default=Decimal("0"))
    tax_due_isk: Mapped[Decimal] = mapped_column(Numeric(20, 2), default=Decimal("0"))
    paid_isk: Mapped[Decimal] = mapped_column(Numeric(20, 2), default=Decimal("0"))
    status: Mapped[str] = mapped_column(String(24), default="open")


class KillboardLeaderboard(Base):
    __tablename__ = "emums_killboard_leaderboard"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    scope: Mapped[str] = mapped_column(String(32), default="alliance")  # corp|alliance
    scope_id: Mapped[int] = mapped_column(BigInteger, index=True)
    period_days: Mapped[int] = mapped_column(Integer, default=30)
    character_id: Mapped[int] = mapped_column(BigInteger, index=True)
    character_name: Mapped[str] = mapped_column(String(128))
    kills: Mapped[int] = mapped_column(Integer, default=0)
    losses: Mapped[int] = mapped_column(Integer, default=0)
    isk_destroyed: Mapped[Decimal] = mapped_column(Numeric(20, 2), default=Decimal("0"))
    isk_lost: Mapped[Decimal] = mapped_column(Numeric(20, 2), default=Decimal("0"))
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )


class PniStatement(Base):
    __tablename__ = "emums_pni_statements"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    period_label: Mapped[str] = mapped_column(String(64))
    status: Mapped[str] = mapped_column(String(24), default="draft")
    total_income_isk: Mapped[Decimal] = mapped_column(Numeric(20, 2), default=Decimal("0"))
    total_expense_isk: Mapped[Decimal] = mapped_column(Numeric(20, 2), default=Decimal("0"))
    payload_json: Mapped[str] = mapped_column(Text, default="{}")


class PniBill(Base):
    __tablename__ = "emums_pni_bills"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    statement_id: Mapped[int] = mapped_column(Integer, index=True)
    bill_type: Mapped[str] = mapped_column(String(64))
    description: Mapped[str] = mapped_column(String(256))
    amount_isk: Mapped[Decimal] = mapped_column(Numeric(20, 2), default=Decimal("0"))
    status: Mapped[str] = mapped_column(String(24), default="open")
    due_at: Mapped[date | None] = mapped_column(Date, nullable=True)


class MarketWatchItem(Base):
    __tablename__ = "emums_market_watch"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    type_id: Mapped[int] = mapped_column(Integer, index=True)
    type_name: Mapped[str] = mapped_column(String(128))
    location_label: Mapped[str] = mapped_column(String(128), default="Jita")
    best_buy: Mapped[Decimal | None] = mapped_column(Numeric(16, 2), nullable=True)
    best_sell: Mapped[Decimal | None] = mapped_column(Numeric(16, 2), nullable=True)
    spread_pct: Mapped[float | None] = mapped_column(Float, nullable=True)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )


class MarketHistoryDay(Base):
    """Cached regional market history from public ESI."""

    __tablename__ = "emums_market_history"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    type_id: Mapped[int] = mapped_column(Integer, index=True)
    region_id: Mapped[int] = mapped_column(Integer, index=True)
    day: Mapped[date] = mapped_column(Date, index=True)
    average: Mapped[float] = mapped_column(Float, default=0.0)
    highest: Mapped[float] = mapped_column(Float, default=0.0)
    lowest: Mapped[float] = mapped_column(Float, default=0.0)
    volume: Mapped[int] = mapped_column(Integer, default=0)
    order_count: Mapped[int] = mapped_column(Integer, default=0)


class SrpRateRule(Base):
    """Admin-configured SRP payout rules per ship / doctrine."""

    __tablename__ = "emums_srp_rate_rules"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    label: Mapped[str] = mapped_column(String(128))
    ship_type_id: Mapped[int] = mapped_column(Integer, default=0, index=True)
    ship_type_name: Mapped[str] = mapped_column(String(128), default="")
    doctrine_slug: Mapped[str] = mapped_column(String(64), default="", index=True)
    base_srp_isk: Mapped[Decimal] = mapped_column(Numeric(20, 2), default=Decimal("0"))
    max_percent: Mapped[Decimal | None] = mapped_column(Numeric(6, 2), nullable=True)
    doctrine_multiplier: Mapped[Decimal] = mapped_column(Numeric(6, 4), default=Decimal("1"))
    meta_multiplier: Mapped[Decimal] = mapped_column(Numeric(6, 4), default=Decimal("0.75"))
    shitfit_multiplier: Mapped[Decimal] = mapped_column(Numeric(6, 4), default=Decimal("0"))
    allow_shitfit: Mapped[bool] = mapped_column(Boolean, default=False)
    enabled: Mapped[bool] = mapped_column(Boolean, default=True, index=True)
    priority: Mapped[int] = mapped_column(Integer, default=100)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )


class SrpLoss(Base):
    __tablename__ = "emums_srp_losses"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    killmail_id: Mapped[int] = mapped_column(BigInteger, unique=True, index=True)
    killmail_hash: Mapped[str] = mapped_column(String(64), default="")
    character_id: Mapped[int] = mapped_column(BigInteger, index=True)
    character_name: Mapped[str] = mapped_column(String(128))
    ship_type_id: Mapped[int] = mapped_column(Integer, default=0)
    ship_type_name: Mapped[str] = mapped_column(String(128), default="")
    total_value_isk: Mapped[Decimal] = mapped_column(Numeric(20, 2), default=Decimal("0"))
    srp_amount_isk: Mapped[Decimal] = mapped_column(Numeric(20, 2), default=Decimal("0"))
    fit_json: Mapped[str] = mapped_column(Text, default="[]")
    fit_grade: Mapped[str] = mapped_column(String(16), default="shitfit", index=True)
    doctrine_slug: Mapped[str] = mapped_column(String(64), default="")
    doctrine_match_pct: Mapped[float] = mapped_column(Float, default=0.0)
    submitted_notes: Mapped[str] = mapped_column(Text, default="")
    status: Mapped[str] = mapped_column(String(24), default="pending", index=True)
    zkill_url: Mapped[str] = mapped_column(String(256), default="")
    solar_system_name: Mapped[str] = mapped_column(String(128), default="")
    killed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    submitted_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    confirmed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))


class RouteBookmark(Base):
    __tablename__ = "emums_route_bookmarks"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    name: Mapped[str] = mapped_column(String(128))
    origin_system: Mapped[str] = mapped_column(String(128))
    destination_system: Mapped[str] = mapped_column(String(128))
    origin_system_id: Mapped[int | None] = mapped_column(Integer, nullable=True)
    destination_system_id: Mapped[int | None] = mapped_column(Integer, nullable=True)
    jumps: Mapped[int] = mapped_column(Integer, default=0)
    route_json: Mapped[str] = mapped_column(Text, default="[]")
    security_max: Mapped[float] = mapped_column(Float, default=1.0)
    route_mode: Mapped[str] = mapped_column(String(16), default="stargate")
    visibility: Mapped[str] = mapped_column(String(16), default="personal")
    payload_json: Mapped[str] = mapped_column(Text, default="{}")
    waypoint_system_ids_json: Mapped[str] = mapped_column(Text, default="[]")
    share_token: Mapped[str | None] = mapped_column(String(32), unique=True, nullable=True, index=True)
    owner_character_id: Mapped[int | None] = mapped_column(BigInteger, nullable=True)
    owner_character_name: Mapped[str] = mapped_column(String(128), default="")
    corporation_id: Mapped[int | None] = mapped_column(BigInteger, nullable=True)
    alliance_id: Mapped[int | None] = mapped_column(BigInteger, nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )


class IndustryCalcJob(Base):
    __tablename__ = "emums_industry_calcs"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    blueprint_type_id: Mapped[int] = mapped_column(Integer, default=0)
    blueprint_name: Mapped[str] = mapped_column(String(128))
    runs: Mapped[int] = mapped_column(Integer, default=1)
    material_cost_isk: Mapped[Decimal] = mapped_column(Numeric(20, 2), default=Decimal("0"))
    product_value_isk: Mapped[Decimal] = mapped_column(Numeric(20, 2), default=Decimal("0"))
    profit_isk: Mapped[Decimal] = mapped_column(Numeric(20, 2), default=Decimal("0"))
    payload_json: Mapped[str] = mapped_column(Text, default="{}")


class CorpMarketListing(Base):
    __tablename__ = "emums_corp_market_listings"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    seller_character_name: Mapped[str] = mapped_column(String(128))
    type_id: Mapped[int] = mapped_column(Integer, index=True)
    type_name: Mapped[str] = mapped_column(String(128))
    quantity: Mapped[int] = mapped_column(Integer, default=1)
    unit_price_isk: Mapped[Decimal] = mapped_column(Numeric(16, 2), default=Decimal("0"))
    listing_type: Mapped[str] = mapped_column(String(24), default="sell")  # sell|buy|haul
    status: Mapped[str] = mapped_column(String(24), default="open", index=True)
    structure_name: Mapped[str] = mapped_column(String(256), default="")
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )


class CorpMarketOrder(Base):
    __tablename__ = "emums_corp_market_orders"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    buyer_character_name: Mapped[str] = mapped_column(String(128))
    buyer_character_id: Mapped[int] = mapped_column(BigInteger, default=0, index=True)
    type_id: Mapped[int] = mapped_column(Integer, index=True)
    type_name: Mapped[str] = mapped_column(String(128))
    quantity: Mapped[int] = mapped_column(Integer, default=1)
    unit_price_isk: Mapped[Decimal] = mapped_column(Numeric(16, 2), default=Decimal("0"))
    total_price_isk: Mapped[Decimal] = mapped_column(Numeric(20, 2), default=Decimal("0"))
    delivery_location: Mapped[str] = mapped_column(String(256), default="")
    notes: Mapped[str] = mapped_column(Text, default="")
    status: Mapped[str] = mapped_column(String(24), default="pending", index=True)
    mail_sent_buyer: Mapped[bool] = mapped_column(Boolean, default=False)
    mail_sent_corp: Mapped[bool] = mapped_column(Boolean, default=False)
    mail_error: Mapped[str] = mapped_column(String(512), default="")
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )


class IndyHubJob(Base):
    __tablename__ = "emums_indy_hub_jobs"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    job_type: Mapped[str] = mapped_column(String(64))
    requester: Mapped[str] = mapped_column(String(128))
    blueprint_name: Mapped[str] = mapped_column(String(128), default="")
    status: Mapped[str] = mapped_column(String(24), default="queued", index=True)
    runs: Mapped[int] = mapped_column(Integer, default=1)
    due_at: Mapped[date | None] = mapped_column(Date, nullable=True)
    notes: Mapped[str] = mapped_column(Text, default="")


class SdeSystem(Base):
    __tablename__ = "emums_sde_systems"

    system_id: Mapped[int] = mapped_column(Integer, primary_key=True)
    name: Mapped[str] = mapped_column(String(128), index=True)
    security: Mapped[float] = mapped_column(Float, default=0.0)
    region_name: Mapped[str] = mapped_column(String(128), default="")
    constellation_name: Mapped[str] = mapped_column(String(128), default="")
    region_id: Mapped[int | None] = mapped_column(Integer, nullable=True)
    constellation_id: Mapped[int | None] = mapped_column(Integer, nullable=True)
    x: Mapped[float | None] = mapped_column(Float, nullable=True)
    y: Mapped[float | None] = mapped_column(Float, nullable=True)
    z: Mapped[float | None] = mapped_column(Float, nullable=True)
    layout_x: Mapped[float | None] = mapped_column(Float, nullable=True)
    layout_y: Mapped[float | None] = mapped_column(Float, nullable=True)


class SdeStargateLink(Base):
    __tablename__ = "emums_sde_stargates"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    from_system_id: Mapped[int] = mapped_column(Integer, index=True)
    to_system_id: Mapped[int] = mapped_column(Integer, index=True)


class SdeSystemActivityHour(Base):
    """Hourly ESI snapshot for Dotlan-style 24h/48h jump and kill rollups."""

    __tablename__ = "emums_sde_system_activity_hours"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    system_id: Mapped[int] = mapped_column(Integer, index=True)
    hour_ts: Mapped[datetime] = mapped_column(DateTime(timezone=True), index=True)
    ship_jumps: Mapped[int] = mapped_column(Integer, default=0)
    ship_kills: Mapped[int] = mapped_column(Integer, default=0)
    pod_kills: Mapped[int] = mapped_column(Integer, default=0)
    npc_kills: Mapped[int] = mapped_column(Integer, default=0)


class IndyBlueprint(Base):
    __tablename__ = "emums_indy_blueprints"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    owner_character_name: Mapped[str] = mapped_column(String(128))
    owner_character_id: Mapped[int | None] = mapped_column(BigInteger, nullable=True, index=True)
    item_id: Mapped[int | None] = mapped_column(BigInteger, nullable=True, unique=True, index=True)
    owner_scope: Mapped[str] = mapped_column(String(16), default="personal")  # personal|corp
    type_id: Mapped[int] = mapped_column(Integer, index=True)
    type_name: Mapped[str] = mapped_column(String(256))
    material_efficiency: Mapped[int] = mapped_column(Integer, default=0)
    time_efficiency: Mapped[int] = mapped_column(Integer, default=0)
    runs: Mapped[int] = mapped_column(Integer, default=-1)
    location_name: Mapped[str] = mapped_column(String(256), default="")
    shared: Mapped[bool] = mapped_column(Boolean, default=False)
    copy_available: Mapped[bool] = mapped_column(Boolean, default=False)


class IndyJobRecord(Base):
    __tablename__ = "emums_indy_job_records"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    character_name: Mapped[str] = mapped_column(String(128), index=True)
    owner_character_id: Mapped[int | None] = mapped_column(BigInteger, nullable=True, index=True)
    installer_id: Mapped[int | None] = mapped_column(BigInteger, nullable=True, index=True)
    installer_name: Mapped[str] = mapped_column(String(128), default="")
    job_id: Mapped[int | None] = mapped_column(BigInteger, nullable=True, index=True)
    blueprint_name: Mapped[str] = mapped_column(String(256))
    activity: Mapped[str] = mapped_column(String(32))  # manufacturing|research|invention|copy
    runs: Mapped[int] = mapped_column(Integer, default=1)
    status: Mapped[str] = mapped_column(String(24), default="active", index=True)
    location_name: Mapped[str] = mapped_column(String(256), default="")
    facility_id: Mapped[int | None] = mapped_column(BigInteger, nullable=True)
    started_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    ends_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    output_type_name: Mapped[str] = mapped_column(String(256), default="")


class CharacterMarketOrder(Base):
    __tablename__ = "emums_character_market_orders"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    character_id: Mapped[int] = mapped_column(BigInteger, index=True)
    character_name: Mapped[str] = mapped_column(String(128), default="")
    order_id: Mapped[int] = mapped_column(BigInteger, unique=True, index=True)
    type_id: Mapped[int] = mapped_column(Integer, index=True)
    type_name: Mapped[str] = mapped_column(String(256))
    is_buy_order: Mapped[bool] = mapped_column(Boolean, default=False)
    price: Mapped[Decimal] = mapped_column(Numeric(16, 2), default=Decimal("0"))
    volume_remain: Mapped[int] = mapped_column(Integer, default=0)
    volume_total: Mapped[int] = mapped_column(Integer, default=0)
    min_volume: Mapped[int] = mapped_column(Integer, default=0)
    location_id: Mapped[int] = mapped_column(BigInteger, default=0)
    location_name: Mapped[str] = mapped_column(String(256), default="")
    range_label: Mapped[str] = mapped_column(String(64), default="")
    issued_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    duration_days: Mapped[int] = mapped_column(Integer, default=0)
    is_corporation: Mapped[bool] = mapped_column(Boolean, default=False)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )

class IndyCopyRequest(Base):
    __tablename__ = "emums_indy_copy_requests"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    requester: Mapped[str] = mapped_column(String(128))
    blueprint_name: Mapped[str] = mapped_column(String(256))
    runs: Mapped[int] = mapped_column(Integer, default=1)
    status: Mapped[str] = mapped_column(String(24), default="open", index=True)
    assignee: Mapped[str] = mapped_column(String(128), default="")
    delivery_location: Mapped[str] = mapped_column(String(256), default="")
    notes: Mapped[str] = mapped_column(Text, default="")
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )


class MaterialExchangeOrder(Base):
    __tablename__ = "emums_material_exchange_orders"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    character_name: Mapped[str] = mapped_column(String(128))
    type_id: Mapped[int] = mapped_column(Integer, index=True)
    type_name: Mapped[str] = mapped_column(String(128))
    side: Mapped[str] = mapped_column(String(8))  # buy|sell
    quantity: Mapped[int] = mapped_column(Integer, default=1)
    unit_price_isk: Mapped[Decimal] = mapped_column(Numeric(16, 2), default=Decimal("0"))
    status: Mapped[str] = mapped_column(String(24), default="pending", index=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )


class IndustrialBuildStructure(Base):
    """Manufacturing locations with bonuses for structure recommendation."""

    __tablename__ = "emums_industrial_build_structures"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    structure_id: Mapped[int] = mapped_column(BigInteger, unique=True, index=True)
    structure_name: Mapped[str] = mapped_column(String(256))
    system_name: Mapped[str] = mapped_column(String(128), default="")
    location_label: Mapped[str] = mapped_column(String(128), default="")
    material_bonus_pct: Mapped[float] = mapped_column(Float, default=0.0)
    time_bonus_pct: Mapped[float] = mapped_column(Float, default=0.0)
    tax_pct: Mapped[float] = mapped_column(Float, default=0.0)
    has_manufacturing: Mapped[bool] = mapped_column(Boolean, default=True)


class IndustrialProject(Base):
    __tablename__ = "emums_industrial_projects"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    project_code: Mapped[str] = mapped_column(String(16), unique=True, index=True)
    name: Mapped[str] = mapped_column(String(256))
    container_name: Mapped[str] = mapped_column(String(256))
    owner_character_name: Mapped[str] = mapped_column(String(128))
    status: Mapped[str] = mapped_column(String(24), default="active", index=True)
    material_cost_isk: Mapped[Decimal] = mapped_column(Numeric(20, 2), default=Decimal("0"))
    job_cost_isk: Mapped[Decimal] = mapped_column(Numeric(20, 2), default=Decimal("0"))
    notes: Mapped[str] = mapped_column(Text, default="")
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )


class ProjectStockAssignment(Base):
    __tablename__ = "emums_project_stock_assignments"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    project_id: Mapped[int] = mapped_column(Integer, index=True)
    type_id: Mapped[int] = mapped_column(Integer, index=True)
    type_name: Mapped[str] = mapped_column(String(128))
    quantity: Mapped[int] = mapped_column(Integer, default=1)
    unit_cost_isk: Mapped[Decimal] = mapped_column(Numeric(16, 2), default=Decimal("0"))
    container_name: Mapped[str] = mapped_column(String(256), default="")


class ProjectJobCost(Base):
    __tablename__ = "emums_project_job_costs"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    project_id: Mapped[int] = mapped_column(Integer, index=True)
    description: Mapped[str] = mapped_column(String(256))
    activity: Mapped[str] = mapped_column(String(32), default="manufacturing")
    runs: Mapped[int] = mapped_column(Integer, default=1)
    cost_isk: Mapped[Decimal] = mapped_column(Numeric(16, 2), default=Decimal("0"))
    structure_name: Mapped[str] = mapped_column(String(256), default="")


class BlueprintPublicContract(Base):
    __tablename__ = "emums_blueprint_public_contracts"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    contract_id: Mapped[int] = mapped_column(BigInteger, index=True)
    blueprint_name: Mapped[str] = mapped_column(String(256))
    seller_name: Mapped[str] = mapped_column(String(128))
    location: Mapped[str] = mapped_column(String(256))
    price_isk: Mapped[Decimal] = mapped_column(Numeric(16, 2), default=Decimal("0"))
    runs: Mapped[int] = mapped_column(Integer, default=1)
    material_efficiency: Mapped[int] = mapped_column(Integer, default=0)
    time_efficiency: Mapped[int] = mapped_column(Integer, default=0)


class StorefrontListing(Base):
    __tablename__ = "emums_storefront_listings"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    seller_character_name: Mapped[str] = mapped_column(String(128))
    type_id: Mapped[int] = mapped_column(Integer, index=True)
    type_name: Mapped[str] = mapped_column(String(128))
    quantity: Mapped[int] = mapped_column(Integer, default=1)
    suggested_price_isk: Mapped[Decimal] = mapped_column(Numeric(16, 2), default=Decimal("0"))
    price_public_isk: Mapped[Decimal] = mapped_column(Numeric(16, 2), default=Decimal("0"))
    price_corp_isk: Mapped[Decimal] = mapped_column(Numeric(16, 2), default=Decimal("0"))
    price_alliance_isk: Mapped[Decimal] = mapped_column(Numeric(16, 2), default=Decimal("0"))
    pricing_mode: Mapped[str] = mapped_column(String(24), default="public")  # public|corp|alliance|standings
    visibility: Mapped[str] = mapped_column(String(24), default="public")
    price_basis: Mapped[str] = mapped_column(String(64), default="alliance_recent")  # market|corp|alliance
    active: Mapped[bool] = mapped_column(Boolean, default=True)
