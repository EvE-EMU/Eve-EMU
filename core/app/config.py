"""Application configuration (``CORE_*`` environment variables)."""

from pydantic import field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_prefix="CORE_", env_file=".env", extra="ignore")

    public_base_url: str = "http://localhost:8000"
    database_url: str | None = None

    sso_client_id: str = ""
    sso_client_secret: str = ""
    sso_authorize_url: str = "https://login.eveonline.com/v2/oauth/authorize"
    sso_token_url: str = "https://login.eveonline.com/v2/oauth/token"
    sso_callback_url: str = "http://localhost:8000/v1/auth/eve/callback"
    sso_scopes: str = (
        "publicData esi-characters.read_corporation_membership.v1 "
        "esi-industry.read_character_mining.v1 esi-contracts.read_character_contracts.v1 "
        "esi-assets.read_assets.v1 esi-markets.structure_markets.v1"
    )

    # Finance plugin: default region for merged NPC-station + structure market browse (The Forge).
    finance_default_region_id: int = 10000002
    finance_region_orders_max_pages: int = 10
    finance_structure_orders_max_pages: int = 3
    finance_sells_max_structure_sources: int = 40
    finance_sells_default_limit: int = 15
    finance_sells_max_limit: int = 50
    # Cheap probe order on structure markets (Tritanium); page-1 GET verifies dock ACL + market module.
    finance_structure_probe_type_id: int = 34

    # Shared secret: Discord bot calls ``POST /v1/integrations/discord/*`` with ``Authorization: Bearer …``.
    discord_bot_secret: str = ""
    # False Gods corporation for rank / ``sync-roles`` (Tranquility corporation ID).
    false_gods_corporation_id: int = 0
    # JSON: list of {"role_id": int, "slug": str, "weight": int} for custom corp roles (highest weight wins).
    fg_rank_roles_json: str = "[]"
    # Optional redirect after successful Discord-linked SSO (browser).
    discord_link_success_url: str = ""

    # Moon tax plugin: contracts must be issued to this assignee id (character or corporation id in ESI).
    moon_tax_assignee_id: int = 0
    # Optional percent of ``owed_total_isk`` (after contract offset) to show as suggested tax (0 = omit).
    moon_tax_percent_of_owed_value: float = 0.0
    # Free text shown in API / Discord (where to contract, how to pay ISK, etc.).
    moon_tax_payment_instructions: str = ""

    openapi_docs_enabled: bool = True
    # Fernet key (url-safe base64 32-byte). Required to encrypt refresh/access tokens in Postgres.
    token_encryption_key: str = ""

    @field_validator("database_url", mode="before")
    @classmethod
    def empty_db_to_none(cls, v: object) -> object:
        if v == "":
            return None
        return v

    @field_validator("false_gods_corporation_id", mode="before")
    @classmethod
    def empty_corp_id(cls, v: object) -> object:
        if v == "" or v is None:
            return 0
        return v

    @field_validator("moon_tax_assignee_id", mode="before")
    @classmethod
    def empty_assignee_id(cls, v: object) -> object:
        if v == "" or v is None:
            return 0
        return v

    @field_validator("finance_default_region_id", mode="before")
    @classmethod
    def empty_finance_region(cls, v: object) -> object:
        if v == "" or v is None:
            return 10000002
        return v


settings = Settings()
