"""Environment-driven settings for fleet.eve-emu.com deployment."""

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_prefix="FLEET_TRACKER_", env_file=".env", extra="ignore")

    public_base_url: str = "https://fleet.eve-emu.com"
    esi_base_url: str = "https://esi.evetech.net/latest"
    sso_authorize_url: str = "https://login.eveonline.com/v2/oauth/authorize"
    sso_token_url: str = "https://login.eveonline.com/v2/oauth/token"
    sso_client_id: str = ""
    sso_client_secret: str = ""
    sso_callback_url: str = "https://fleet.eve-emu.com/auth/callback"
    # Space-separated scopes for participant linking (extend as features land).
    sso_default_scopes: str = (
        "esi-fleets.read_fleet.v1 "
        "esi-location.read_location.v1 "
        "esi-ships.read_ships.v1 "
        "esi-killmails.read_killmails.v1"
    )
    # Optional FC account scopes (separate client or override scopes in UI).
    sso_fc_scopes: str = "esi-fleets.read_fleet_information.v1"
    # Heuristic / config for “WOMP Standing” detection (implement in service layer).
    womp_fleet_motd_substrings: str = "WOMP,Standing"
    womp_alliance_id: int = 99010468


settings = Settings()
