from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_prefix="REPORT_", env_file=".env", extra="ignore")

    esi_forwarder_url: str = "http://aa-web:8080"
    esi_forwarder_secret: str = ""
    default_token_id: int = 0
    public_base_url: str = "https://eve-emu.com"
    connections_file: str = "data/connections.json"
    history_db: str = "data/history/events.sqlite"
    admin_api_key: str = ""


settings = Settings()
