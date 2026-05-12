"""ORM models: users, OAuth tokens (Postgres + Docker volume = survives container restarts)."""

from __future__ import annotations

import uuid
from datetime import UTC, datetime

from sqlalchemy import BigInteger, DateTime, ForeignKey, LargeBinary, String, Text
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column


class Base(DeclarativeBase):
    pass


class CoreUser(Base):
    """Stable eve-emu account; one row per linked EVE paying account (see ``EveLinkedCharacter.owner_hash``)."""

    __tablename__ = "core_users"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    # Discord snowflake for bot role sync (one Discord user per core account).
    discord_user_id: Mapped[int | None] = mapped_column(BigInteger, unique=True, nullable=True, index=True)
    # Which character is "main" for UI and defaults; must belong to this user in eve_linked_characters.
    main_character_id: Mapped[int | None] = mapped_column(
        BigInteger,
        ForeignKey("eve_linked_characters.character_id", ondelete="SET NULL", use_alter=True),
        nullable=True,
        index=True,
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        default=lambda: datetime.now(UTC),
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        default=lambda: datetime.now(UTC),
    )


class DiscordPendingSsoLink(Base):
    """Browser SSO started from Discord ``/settings link``; ``state`` sent to CCP is ``link_id``."""

    __tablename__ = "discord_pending_sso_links"

    link_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    discord_user_id: Mapped[int] = mapped_column(BigInteger, nullable=False, index=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        default=lambda: datetime.now(UTC),
    )


class EveLinkedCharacter(Base):
    """Characters attached to a ``CoreUser``; ``character_id`` is the stable key (names can change)."""

    __tablename__ = "eve_linked_characters"

    character_id: Mapped[int] = mapped_column(BigInteger, primary_key=True)
    user_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("core_users.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    # From EVE SSO JWT ``owner`` claim; identical for all characters on the same EVE account.
    owner_hash: Mapped[str] = mapped_column(String(255), nullable=False, index=True)
    character_name: Mapped[str] = mapped_column(String(255), nullable=False, default="")
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        default=lambda: datetime.now(UTC),
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        default=lambda: datetime.now(UTC),
    )


class EveOAuthToken(Base):
    """EVE SSO refresh (and optional access) tokens, encrypted at rest."""

    __tablename__ = "eve_oauth_tokens"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    character_id: Mapped[int] = mapped_column(BigInteger, unique=True, nullable=False, index=True)
    owner_user_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("core_users.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )
    refresh_token_enc: Mapped[bytes] = mapped_column(LargeBinary, nullable=False)
    access_token_enc: Mapped[bytes | None] = mapped_column(LargeBinary, nullable=True)
    access_expires_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    scopes: Mapped[str] = mapped_column(Text, nullable=False, default="")
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        default=lambda: datetime.now(UTC),
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        default=lambda: datetime.now(UTC),
    )


class FinanceMarketStructure(Base):
    """Player structure IDs whose markets were verified via an authed character (``esi-markets.structure_markets.v1``)."""

    __tablename__ = "finance_market_structures"

    structure_id: Mapped[int] = mapped_column(BigInteger, primary_key=True)
    structure_name: Mapped[str] = mapped_column(String(512), nullable=False, default="")
    solar_system_id: Mapped[int | None] = mapped_column(BigInteger, nullable=True, index=True)
    region_id: Mapped[int | None] = mapped_column(BigInteger, nullable=True, index=True)
    witness_character_id: Mapped[int] = mapped_column(BigInteger, nullable=False, index=True)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        default=lambda: datetime.now(UTC),
    )
