"""Member audit ESI snapshots and service sync configuration."""

from __future__ import annotations

from datetime import datetime
from decimal import Decimal

from sqlalchemy import BigInteger, Boolean, DateTime, ForeignKey, Integer, Numeric, String, Text, UniqueConstraint, func
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base


class CharacterWalletJournal(Base):
    __tablename__ = "emums_character_wallet_journals"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    character_id: Mapped[int] = mapped_column(BigInteger, index=True)
    journal_id: Mapped[int] = mapped_column(BigInteger, unique=True, index=True)
    ref_type: Mapped[str] = mapped_column(String(64), default="", index=True)
    amount: Mapped[Decimal] = mapped_column(Numeric(20, 2), default=Decimal("0"))
    balance: Mapped[Decimal] = mapped_column(Numeric(20, 2), default=Decimal("0"))
    first_party_id: Mapped[int | None] = mapped_column(BigInteger, nullable=True)
    second_party_id: Mapped[int | None] = mapped_column(BigInteger, nullable=True, index=True)
    reason: Mapped[str] = mapped_column(String(512), default="")
    recorded_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), index=True)


class CharacterAsset(Base):
    __tablename__ = "emums_character_assets"
    __table_args__ = (
        UniqueConstraint("character_id", "item_id", name="uq_emums_character_assets_char_item"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    character_id: Mapped[int] = mapped_column(BigInteger, index=True)
    item_id: Mapped[int] = mapped_column(BigInteger, index=True)
    type_id: Mapped[int] = mapped_column(Integer, index=True)
    type_name: Mapped[str] = mapped_column(String(256), default="")
    quantity: Mapped[int] = mapped_column(Integer, default=1)
    location_id: Mapped[int] = mapped_column(BigInteger, default=0)
    flag: Mapped[str] = mapped_column(String(32), default="")
    custom_name: Mapped[str] = mapped_column(String(256), default="")
    synced_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )


class UniverseLocation(Base):
    """Cached station/structure/system names from ESI."""

    __tablename__ = "emums_universe_locations"

    entity_id: Mapped[int] = mapped_column(BigInteger, primary_key=True)
    name: Mapped[str] = mapped_column(String(256), default="")
    entity_type: Mapped[str] = mapped_column(String(32), default="")
    solar_system_id: Mapped[int | None] = mapped_column(Integer, nullable=True, index=True)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )


class AuditSecurityFlag(Base):
    __tablename__ = "emums_audit_security_flags"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    character_id: Mapped[int] = mapped_column(BigInteger, index=True)
    character_name: Mapped[str] = mapped_column(String(128), default="")
    flag_key: Mapped[str] = mapped_column(String(64), index=True)
    severity: Mapped[str] = mapped_column(String(16), default="warn")
    detail: Mapped[str] = mapped_column(Text, default="")
    resolved: Mapped[bool] = mapped_column(Boolean, default=False, index=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), index=True
    )


class CharacterInteractionAggregate(Base):
    """Pre-aggregated contact counts per character × counterparty × channel."""

    __tablename__ = "emums_character_interaction_aggregates"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    owner_user_id: Mapped[int] = mapped_column(Integer, index=True)
    character_id: Mapped[int] = mapped_column(BigInteger, index=True)
    counterparty_id: Mapped[int] = mapped_column(BigInteger, index=True)
    counterparty_kind: Mapped[str] = mapped_column(String(16), default="entity", index=True)
    counterparty_name: Mapped[str] = mapped_column(String(256), default="")
    channel: Mapped[str] = mapped_column(String(32), index=True)
    event_count: Mapped[int] = mapped_column(Integer, default=0)
    first_seen_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    last_seen_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True, index=True)
    last_detail: Mapped[str] = mapped_column(String(512), default="")
    total_amount_isk: Mapped[Decimal] = mapped_column(Numeric(20, 2), default=Decimal("0"))
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )


class IntelEntityTag(Base):
    """Manual intel tags — spy alts, holding corps, watchlist, etc."""

    __tablename__ = "emums_intel_entity_tags"
    __table_args__ = (
        UniqueConstraint(
            "owner_user_id",
            "entity_id",
            "tag_type",
            name="uq_intel_tag_owner_entity_type",
        ),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    owner_user_id: Mapped[int] = mapped_column(Integer, index=True)
    entity_id: Mapped[int] = mapped_column(BigInteger, index=True)
    entity_kind: Mapped[str] = mapped_column(String(16), default="character")
    entity_name: Mapped[str] = mapped_column(String(256), default="")
    tag_type: Mapped[str] = mapped_column(String(32), index=True)
    # Optional: who this entity is believed to be an alt of
    linked_character_id: Mapped[int | None] = mapped_column(BigInteger, nullable=True, index=True)
    linked_character_name: Mapped[str] = mapped_column(String(128), default="")
    notes: Mapped[str] = mapped_column(Text, default="")
    created_by_character_id: Mapped[int] = mapped_column(BigInteger, default=0)
    created_by_character_name: Mapped[str] = mapped_column(String(128), default="")
    active: Mapped[bool] = mapped_column(Boolean, default=True, index=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )


class HrAuditAlertRule(Base):
    """HR-configurable audit alert rules with optional Discord/webhook delivery."""

    __tablename__ = "emums_hr_audit_alert_rules"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    rule_key: Mapped[str] = mapped_column(String(64), unique=True, index=True)
    name: Mapped[str] = mapped_column(String(128))
    description: Mapped[str] = mapped_column(Text, default="")
    enabled: Mapped[bool] = mapped_column(Boolean, default=True, index=True)
    severity: Mapped[str] = mapped_column(String(16), default="warn")
    rule_type: Mapped[str] = mapped_column(String(32), index=True)
    match_json: Mapped[str] = mapped_column(Text, default="{}")
    webhook_url: Mapped[str] = mapped_column(String(512), default="")
    notify_in_app: Mapped[bool] = mapped_column(Boolean, default=True)
    cooldown_hours: Mapped[int] = mapped_column(Integer, default=24)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )


class HrAuditAlertEvent(Base):
    """Delivery log for HR audit alerts (webhook + in-app)."""

    __tablename__ = "emums_hr_audit_alert_events"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    rule_id: Mapped[int | None] = mapped_column(Integer, nullable=True, index=True)
    character_id: Mapped[int] = mapped_column(BigInteger, index=True)
    character_name: Mapped[str] = mapped_column(String(128), default="")
    flag_key: Mapped[str] = mapped_column(String(128), index=True)
    severity: Mapped[str] = mapped_column(String(16), default="warn")
    detail: Mapped[str] = mapped_column(Text, default="")
    webhook_status: Mapped[str] = mapped_column(String(32), default="skipped")
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), index=True
    )


class WebhookNotificationRule(Base):
    """User-configurable webhook alerts tied to audit/ESI snapshot events."""

    __tablename__ = "emums_webhook_notification_rules"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    owner_user_id: Mapped[int] = mapped_column(Integer, index=True)
    created_by_character_id: Mapped[int] = mapped_column(BigInteger, index=True)
    name: Mapped[str] = mapped_column(String(128))
    description: Mapped[str] = mapped_column(Text, default="")
    enabled: Mapped[bool] = mapped_column(Boolean, default=True, index=True)
    event_type: Mapped[str] = mapped_column(String(64), index=True)
    match_json: Mapped[str] = mapped_column(Text, default="{}")
    webhook_url: Mapped[str] = mapped_column(String(512), default="")
    notify_in_app: Mapped[bool] = mapped_column(Boolean, default=True)
    delivery_mode: Mapped[str] = mapped_column(String(16), default="instant", index=True)
    all_characters: Mapped[bool] = mapped_column(Boolean, default=True)
    target_character_id: Mapped[int | None] = mapped_column(BigInteger, nullable=True, index=True)
    last_digest_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )


class WebhookNotificationPending(Base):
    """Buffered events waiting for digest delivery."""

    __tablename__ = "emums_webhook_notification_pending"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    rule_id: Mapped[int] = mapped_column(Integer, index=True)
    character_id: Mapped[int] = mapped_column(BigInteger, index=True)
    character_name: Mapped[str] = mapped_column(String(128), default="")
    event_key: Mapped[str] = mapped_column(String(128), index=True)
    title: Mapped[str] = mapped_column(String(256))
    body: Mapped[str] = mapped_column(Text, default="")
    payload_json: Mapped[str] = mapped_column(Text, default="{}")
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), index=True
    )


class WebhookNotificationDelivery(Base):
    """Delivery log for webhook notification rules."""

    __tablename__ = "emums_webhook_notification_deliveries"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    rule_id: Mapped[int] = mapped_column(Integer, index=True)
    character_id: Mapped[int] = mapped_column(BigInteger, index=True)
    delivery_mode: Mapped[str] = mapped_column(String(16), default="instant")
    event_count: Mapped[int] = mapped_column(Integer, default=1)
    webhook_status: Mapped[str] = mapped_column(String(32), default="skipped")
    detail: Mapped[str] = mapped_column(Text, default="")
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), index=True
    )


class ServiceSyncConfig(Base):
    __tablename__ = "emums_service_sync_config"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    discord_bot_token: Mapped[str] = mapped_column(Text, default="")
    discord_guild_id: Mapped[str] = mapped_column(String(32), default="")
    discord_nickname_format: Mapped[str] = mapped_column(String(128), default="[{ticker}] {name}")
    mumble_server_json: Mapped[str] = mapped_column(Text, default="{}")
    enabled: Mapped[bool] = mapped_column(Boolean, default=False)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )


class UserServiceSyncState(Base):
    __tablename__ = "emums_user_service_sync"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    character_id: Mapped[int] = mapped_column(BigInteger, unique=True, index=True)
    last_sync_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    last_error: Mapped[str] = mapped_column(Text, default="")
    discord_roles_json: Mapped[str] = mapped_column(Text, default="[]")
