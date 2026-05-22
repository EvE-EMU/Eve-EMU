"""Cached market data for public tools (WOMPSTAR + import regions)."""

from __future__ import annotations

from datetime import date, datetime

from sqlalchemy import (
    BigInteger,
    Boolean,
    Date,
    DateTime,
    Float,
    Index,
    Integer,
    String,
    Text,
    UniqueConstraint,
    func,
)
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column


class Base(DeclarativeBase):
    pass


class MarketLocation(Base):
    """Structure or station scope for queries."""

    __tablename__ = "market_locations"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    location_id: Mapped[int] = mapped_column(BigInteger, unique=True, index=True)
    kind: Mapped[str] = mapped_column(String(16))  # structure | station | region
    name: Mapped[str] = mapped_column(String(256), default="")
    region_id: Mapped[int | None] = mapped_column(Integer, nullable=True)
    is_primary: Mapped[bool] = mapped_column(Boolean, default=False)


class MarketOrder(Base):
    __tablename__ = "market_orders"
    __table_args__ = (
        UniqueConstraint("order_id", name="uq_market_orders_order_id"),
        Index("ix_market_orders_type_location", "type_id", "location_id"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    order_id: Mapped[int] = mapped_column(BigInteger)
    location_id: Mapped[int] = mapped_column(BigInteger, index=True)
    type_id: Mapped[int] = mapped_column(Integer, index=True)
    is_buy: Mapped[bool] = mapped_column(Boolean)
    price: Mapped[float] = mapped_column(Float)
    volume_remain: Mapped[int] = mapped_column(BigInteger)
    volume_total: Mapped[int] = mapped_column(BigInteger, default=0)
    min_volume: Mapped[int] = mapped_column(Integer, default=1)
    range: Mapped[str] = mapped_column(String(32), default="station")
    issued: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    duration: Mapped[int] = mapped_column(Integer, default=0)
    synced_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )


class MarketGroup(Base):
    """EVE market group hierarchy (ESI universe/groups)."""

    __tablename__ = "market_groups"

    group_id: Mapped[int] = mapped_column(Integer, primary_key=True)
    name: Mapped[str] = mapped_column(String(256))
    parent_group_id: Mapped[int | None] = mapped_column(Integer, nullable=True, index=True)


class MarketCatalogType(Base):
    """All published marketable types (EVE Ref), grouped by market_group_id."""

    __tablename__ = "market_catalog_types"
    __table_args__ = (Index("ix_market_catalog_types_group", "market_group_id"),)

    type_id: Mapped[int] = mapped_column(Integer, primary_key=True)
    market_group_id: Mapped[int] = mapped_column(Integer, index=True)
    name: Mapped[str] = mapped_column(String(256))
    name_lower: Mapped[str] = mapped_column(String(256))


class MarketType(Base):
    """Inventory type names for items listed at a hub (from ESI universe/names)."""

    __tablename__ = "market_types"
    __table_args__ = (
        Index("ix_market_types_name_lower", "name_lower"),
        Index("ix_market_types_location", "location_id"),
    )

    type_id: Mapped[int] = mapped_column(Integer, primary_key=True)
    location_id: Mapped[int] = mapped_column(BigInteger, index=True)
    name: Mapped[str] = mapped_column(String(256))
    name_lower: Mapped[str] = mapped_column(String(256))
    market_group_id: Mapped[int | None] = mapped_column(Integer, nullable=True, index=True)


class MarketHistoryDay(Base):
    __tablename__ = "market_history_days"
    __table_args__ = (
        UniqueConstraint("type_id", "region_id", "day", name="uq_history_type_region_day"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    type_id: Mapped[int] = mapped_column(Integer, index=True)
    region_id: Mapped[int] = mapped_column(Integer, index=True)
    day: Mapped[date] = mapped_column(Date)
    average: Mapped[float] = mapped_column(Float, default=0)
    highest: Mapped[float] = mapped_column(Float, default=0)
    lowest: Mapped[float] = mapped_column(Float, default=0)
    volume: Mapped[int] = mapped_column(BigInteger, default=0)
    order_count: Mapped[int] = mapped_column(Integer, default=0)


class MarketContract(Base):
    """Cached corporation contracts (WOMP shop / alliance sales)."""

    __tablename__ = "market_contracts"

    contract_id: Mapped[int] = mapped_column(BigInteger, primary_key=True)
    issuer_corp_id: Mapped[int] = mapped_column(Integer, index=True)
    contract_type: Mapped[str] = mapped_column(String(32), index=True)
    status: Mapped[str] = mapped_column(String(32), index=True)
    availability: Mapped[str] = mapped_column(String(32), default="")
    title: Mapped[str] = mapped_column(String(512), default="")
    price: Mapped[float] = mapped_column(Float, default=0)
    date_issued: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    date_expired: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    synced_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )


class MarketContractItem(Base):
    __tablename__ = "market_contract_items"
    __table_args__ = (
        Index("ix_market_contract_items_contract", "contract_id"),
        Index("ix_market_contract_items_type", "type_id"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    contract_id: Mapped[int] = mapped_column(BigInteger, index=True)
    type_id: Mapped[int] = mapped_column(Integer, index=True)
    quantity: Mapped[int] = mapped_column(BigInteger, default=1)
    is_blueprint_copy: Mapped[bool] = mapped_column(Boolean, default=False)
    me: Mapped[int] = mapped_column(Integer, default=0)
    te: Mapped[int] = mapped_column(Integer, default=0)


class ContractPriceDay(Base):
    """WOMP alliance contract price grid (BPC / items) by day."""

    __tablename__ = "contract_price_days"
    __table_args__ = (
        UniqueConstraint(
            "type_id", "region_id", "day", "me", "te", name="uq_contract_price_day"
        ),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    type_id: Mapped[int] = mapped_column(Integer, index=True)
    region_id: Mapped[int] = mapped_column(Integer, index=True)
    day: Mapped[date] = mapped_column(Date)
    me: Mapped[int] = mapped_column(Integer, default=0)
    te: Mapped[int] = mapped_column(Integer, default=0)
    price: Mapped[float] = mapped_column(Float)
    volume: Mapped[int] = mapped_column(BigInteger, default=0)
    count: Mapped[int] = mapped_column(Integer, default=0)


class TypeAppraisal(Base):
    """Persisted appraisal / pricing snapshot (browser + buyback hints)."""

    __tablename__ = "type_appraisals"
    __table_args__ = (Index("ix_type_appraisals_type", "type_id"),)

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    type_id: Mapped[int] = mapped_column(Integer, index=True)
    wompstar_sell: Mapped[float | None] = mapped_column(Float, nullable=True)
    wompstar_buy: Mapped[float | None] = mapped_column(Float, nullable=True)
    jita_sell: Mapped[float | None] = mapped_column(Float, nullable=True)
    jita_buy: Mapped[float | None] = mapped_column(Float, nullable=True)
    amarr_sell: Mapped[float | None] = mapped_column(Float, nullable=True)
    amarr_buy: Mapped[float | None] = mapped_column(Float, nullable=True)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )


class SyncRun(Base):
    __tablename__ = "sync_runs"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    job: Mapped[str] = mapped_column(String(64), index=True)
    started_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    finished_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    ok: Mapped[bool] = mapped_column(Boolean, default=True)
    detail: Mapped[str] = mapped_column(Text, default="")
