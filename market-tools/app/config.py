"""Market tools configuration (``MARKET_*`` environment variables)."""

from pydantic import field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_prefix="MARKET_", env_file=".env", extra="ignore")

    public_base_url: str = "https://eve-emu.com"
    database_url: str = (
        "postgresql+asyncpg://eve:eve@db:5432/eve_emu_market"
    )
    redis_url: str = "redis://redis:6379/2"

    # Use Alliance Auth django-esi token (Sevey token #41 with structure_markets) via internal bridge.
    use_aa_token: bool = True
    aa_token_bridge_url: str = "http://aa-web:8080/internal/market/access-token"
    internal_secret: str = ""
    esi_token_id: int = 41
    esi_character_name: str = "Sevey"

    # Optional: standalone CCP app + refresh token instead of AA bridge.
    esi_client_id: str = ""
    esi_client_secret: str = ""
    esi_refresh_token: str = ""

    # W O M P S T A R — player-owned market (structure ID from in-game show info).
    wompstar_structure_id: int = 0
    wompstar_structure_name: str = "3-FKCZ - W O M P S T A R"
    wompstar_system_id: int = 30004019  # 3-FKCZ → Querious region via ESI
    wompstar_region_id: int = 10000050  # Querious; auto-resolved from system if unset

    # Default import/compare hub (The Forge / Jita).
    default_import_region_id: int = 10000002
    default_import_station_id: int = 60003760

    # WOMP alliance contracts (issuer corp id).
    womp_alliance_id: int = 0
    womp_contract_issuer_corp_id: int = 0

    # Internal buyback (Alliance Auth public calculator).
    buyback_public_url: str = "https://auth.eve-emu.com/buyback_v2/"

    # ESI pacing (Tranquility error-limit aware).
    esi_max_concurrent: int = 4
    esi_min_interval_seconds: float = 0.12
    structure_orders_sync_interval_minutes: int = 10
    region_history_sync_interval_hours: int = 6

    openapi_docs_enabled: bool = True
    sync_enabled: bool = True

    @field_validator(
        "wompstar_structure_id",
        "wompstar_system_id",
        "womp_contract_issuer_corp_id",
        "womp_alliance_id",
        "esi_token_id",
        mode="before",
    )
    @classmethod
    def empty_int(cls, v: object) -> object:
        if v == "" or v is None:
            return 0
        return v

    def esi_configured(self) -> bool:
        rt = (self.esi_refresh_token or "").strip()
        if self.esi_client_id and rt and not rt.startswith("#"):
            return True
        return bool(
            self.use_aa_token
            and self.internal_secret
            and self.aa_token_bridge_url
            and (self.esi_token_id or self.esi_character_name)
        )


settings = Settings()
