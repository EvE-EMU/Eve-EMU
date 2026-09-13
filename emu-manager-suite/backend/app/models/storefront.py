"""Corp storefront — inventory, kits, orders."""

from __future__ import annotations

from datetime import datetime
from decimal import Decimal

from sqlalchemy import BigInteger, Boolean, DateTime, ForeignKey, Integer, Numeric, String, Text, func
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base


class StorefrontConfig(Base):
    """Singleton-style storefront configuration."""

    __tablename__ = "emums_storefront_config"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    enabled: Mapped[bool] = mapped_column(Boolean, default=True)
    corp_name: Mapped[str] = mapped_column(String(128), default="Solar Extraction Venture")
    corp_id: Mapped[int] = mapped_column(BigInteger, default=0)
    inventory_character_ids: Mapped[str] = mapped_column(
        String(512), default=""
    )  # comma-separated ESI character IDs whose asset sync includes corp hangar
    corp_hangar_flag: Mapped[str] = mapped_column(String(32), default="CorpSAG1")
    structure_id: Mapped[int] = mapped_column(BigInteger, default=0)
    structure_name_contains: Mapped[str] = mapped_column(String(128), default="")
    system_name_contains: Mapped[str] = mapped_column(String(64), default="")
    price_hub: Mapped[str] = mapped_column(String(32), default="jita")
    discord_webhook_url: Mapped[str] = mapped_column(String(512), default="")
    staff_notify_character_id: Mapped[int] = mapped_column(BigInteger, default=0)
    contract_expiration_hours: Mapped[int] = mapped_column(Integer, default=24)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )


class StorefrontPickupLocation(Base):
    __tablename__ = "emums_storefront_pickup_locations"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    label: Mapped[str] = mapped_column(String(128))
    structure_name: Mapped[str] = mapped_column(String(256), default="")
    structure_id: Mapped[int] = mapped_column(BigInteger, default=0)
    system_name: Mapped[str] = mapped_column(String(64), default="")
    location_hint: Mapped[str] = mapped_column(String(512), default="")
    is_default: Mapped[bool] = mapped_column(Boolean, default=False)
    active: Mapped[bool] = mapped_column(Boolean, default=True)
    sort_order: Mapped[int] = mapped_column(Integer, default=0)


class StorefrontItemOverride(Base):
    __tablename__ = "emums_storefront_item_overrides"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    type_id: Mapped[int] = mapped_column(Integer, unique=True, index=True)
    type_name: Mapped[str] = mapped_column(String(256), default="")
    price_override_isk: Mapped[Decimal | None] = mapped_column(Numeric(16, 2), nullable=True)
    fake_qty_add: Mapped[int] = mapped_column(Integer, default=0)
    hidden: Mapped[bool] = mapped_column(Boolean, default=False)
    note: Mapped[str] = mapped_column(String(512), default="")


class StorefrontKit(Base):
    __tablename__ = "emums_storefront_kits"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    name: Mapped[str] = mapped_column(String(256))
    description: Mapped[str] = mapped_column(Text, default="")
    price_isk: Mapped[Decimal | None] = mapped_column(Numeric(16, 2), nullable=True)
    active: Mapped[bool] = mapped_column(Boolean, default=True)
    sort_order: Mapped[int] = mapped_column(Integer, default=0)
    items: Mapped[list[StorefrontKitItem]] = relationship(
        back_populates="kit", cascade="all, delete-orphan"
    )


class StorefrontKitItem(Base):
    __tablename__ = "emums_storefront_kit_items"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    kit_id: Mapped[int] = mapped_column(ForeignKey("emums_storefront_kits.id", ondelete="CASCADE"), index=True)
    type_id: Mapped[int] = mapped_column(Integer, index=True)
    type_name: Mapped[str] = mapped_column(String(256), default="")
    quantity: Mapped[int] = mapped_column(Integer, default=1)
    kit: Mapped[StorefrontKit] = relationship(back_populates="items")


class StorefrontOrder(Base):
    __tablename__ = "emums_storefront_orders"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    order_code: Mapped[str] = mapped_column(String(32), unique=True, index=True)
    buyer_character_id: Mapped[int] = mapped_column(BigInteger, default=0, index=True)
    buyer_character_name: Mapped[str] = mapped_column(String(128))
    pickup_location_id: Mapped[int | None] = mapped_column(Integer, nullable=True)
    pickup_label: Mapped[str] = mapped_column(String(128), default="")
    lines_json: Mapped[str] = mapped_column(Text, default="[]")
    total_isk: Mapped[Decimal] = mapped_column(Numeric(20, 2), default=Decimal("0"))
    contract_description: Mapped[str] = mapped_column(String(256), default="")
    status: Mapped[str] = mapped_column(String(24), default="pending", index=True)
    mail_sent_buyer: Mapped[bool] = mapped_column(Boolean, default=False)
    mail_sent_corp: Mapped[bool] = mapped_column(Boolean, default=False)
    discord_sent: Mapped[bool] = mapped_column(Boolean, default=False)
    webhook_sent: Mapped[bool] = mapped_column(Boolean, default=False)
    mail_error: Mapped[str] = mapped_column(String(2000), default="")
    notes: Mapped[str] = mapped_column(Text, default="")
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), index=True
    )
