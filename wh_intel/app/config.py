"""WH intel overlay configuration (``WH_INTEL_*`` env vars)."""

from pydantic import field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_prefix="WH_INTEL_", env_file=".env", extra="ignore")

    database_url: str = "postgresql+asyncpg://eve:eve@db:5432/eve_emu_wh_intel"
    public_base_url: str = "https://wh.eve-emu.com/intel"

    # Comma-separated EVE chat channel names (case-insensitive).
    channels: str = "intel.womp,OnlyQuerious"

    # How long a system ping ring stays visible (RIFT-style).
    ring_ttl_seconds: int = 300

    # Optional gate bubble default TTL (0 = until removed).
    bubble_ttl_seconds: int = 0

    # Alliance IDs for sov tag resolution (comma-separated).
    sov_alliance_ids: str = "99010468"

    # Optional Fuzzwork SQLite for map x/y + jumps (offline layout).
    sde_sqlite_path: str = ""

    esi_base_url: str = "https://esi.evetech.net/latest"
    esi_datasource: str = "tranquility"

    # --- Wanderer auto-sync (https://wh.<domain>/ map API) ---
    wanderer_sync: bool = True
    wanderer_base_url: str = "https://wh.eve-emu.com"
    wanderer_map_slug: str = "false-gods"
    wanderer_api_token: str = ""
    wanderer_database_url: str = "postgresql+asyncpg://eve:eve@db:5432/wanderer"
    wanderer_db_ping_sync: bool = False  # WH_INTEL_WANDERER_DB_PING_SYNC
    wanderer_ping_character_eve_id: int = 0

    @field_validator("channels", "sov_alliance_ids", mode="before")
    @classmethod
    def _strip(cls, v: object) -> str:
        return str(v or "").strip()

    def channel_set(self) -> set[str]:
        return {c.strip().lower() for c in self.channels.split(",") if c.strip()}

    def sov_alliance_id_list(self) -> list[int]:
        out: list[int] = []
        for part in self.sov_alliance_ids.split(","):
            part = part.strip()
            if part.isdigit():
                out.append(int(part))
        return out


settings = Settings()
