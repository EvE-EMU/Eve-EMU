"""Runtime configuration via environment variables."""

from __future__ import annotations

from functools import lru_cache

from pydantic_settings import BaseSettings, SettingsConfigDict

from app.audit_scope_constants import DEFAULT_SSO_SCOPES_STRING


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_prefix="EMUMS_", env_file=".env", extra="ignore")

    app_name: str = "EMU Manager Suite"
    environment: str = "test"
    debug: bool = False
    public_base_url: str = "https://emums.eve-emu.com"
    api_prefix: str = "/v1"

    database_url: str = (
        "mysql+aiomysql://emums:emums@emums-mysql:3306/emums?charset=utf8mb4"
    )
    redis_url: str = "redis://emums-redis:6379/0"

    api_key: str = "emums-dev-key-change-me"
    openapi_docs_enabled: bool = True
    seed_demo_data: bool = True

    # Fuzzwork SDE SQLite (mapSolarSystems + mapSolarSystemJumps)
    sde_sqlite_path: str = "/data/sde/latest-sqlite.db"

    cors_origins: str = "https://emums.eve-emu.com,http://localhost:3020"

    uploads_path: str = "/data/uploads"
    max_upload_mb: int = 100

    # EVE SSO / ESI integration
    sso_client_id: str = ""
    sso_client_secret: str = ""
    sso_callback_url: str = "https://emums.eve-emu.com/api/auth/callback"
    sso_scopes: str = DEFAULT_SSO_SCOPES_STRING
    audit_sync_interval_minutes: int = 30
    audit_sync_stale_minutes: int = 25
    audit_sync_batch_size: int = 200
    db_pool_size: int = 20
    db_max_overflow: int = 40
    interaction_journal_days: int = 180
    interaction_journal_max_rows: int = 5000
    roster_overview_cache_seconds: int = 20
    session_secret: str = ""
    session_ttl_seconds: int = 60 * 60 * 24 * 30
    esi_refresh_token: str = ""
    aa_api_base_url: str = "https://auth.eve-emu.com"
    esi_base_url: str = "https://esi.evetech.net/latest"

    # Pricing / market
    janice_api_key: str = ""
    janice_instant_prices: bool = False
    a4e_enabled: bool = True
    a4e_base_url: str = "https://api.adam4eve.eu/v1"
    a4e_min_interval_seconds: float = 5.0
    a4e_user_agent: str = "EVE-EMU-EMUMS/1.0 (+https://emums.eve-emu.com; market-browser)"
    wompstar_structure_id: int = 1051567430261
    wompstar_structure_name: str = (
        "3T7-M8 - Citadel of the Holy Procurer (Alpha Republic - Transcenders of Space and Time)"
    )
    market_api_internal_url: str = "http://prod-market-api:8010"
    default_buyback_fee_pct: float = 90.0
    corp_market_notify_character_id: int = 0

    # Killboard scope (Slyce / coalition)
    killboard_alliance_id: int = 1042504553
    killboard_alliance_name: str = "Slyce"
    killboard_corporation_id: int = 98799892

    # zKillboard
    zkill_base_url: str = "https://zkillboard.com/api"

    # MediaWiki (SDE knowledge base)
    mediawiki_api_url: str = "https://wiki.eve-emu.com/api.php"
    mediawiki_public_url: str = "https://wiki.eve-emu.com"
    mediawiki_bot_user: str = ""
    mediawiki_bot_password: str = ""

    @property
    def max_upload_bytes(self) -> int:
        return self.max_upload_mb * 1024 * 1024

    @property
    def cors_origin_list(self) -> list[str]:
        return [o.strip() for o in self.cors_origins.split(",") if o.strip()]


@lru_cache
def get_settings() -> Settings:
    return Settings()


settings = get_settings()
