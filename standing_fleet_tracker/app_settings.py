import os


def _env(name: str, default: str = "") -> str:
    return os.environ.get(name, default).strip()


def _env_int(name: str, default: int) -> int:
    raw = _env(name, str(default))
    try:
        return int(raw)
    except ValueError:
        return default


def _env_float(name: str, default: float) -> float:
    raw = _env(name, str(default))
    try:
        return float(raw)
    except ValueError:
        return default


SFT_ALLIANCE_ID = _env_int("SFT_ALLIANCE_ID", 99010468)
SFT_POLL_INTERVAL_SECONDS = _env_int("SFT_POLL_INTERVAL_SECONDS", 300)
SFT_MAX_CHARACTERS_PER_POLL = _env_int("SFT_MAX_CHARACTERS_PER_POLL", 40)
SFT_STANDING_MOTD_SUBSTRINGS = [
    s.strip() for s in _env("SFT_STANDING_MOTD_SUBSTRINGS", "WOMP,Standing,STANDING").split(",") if s.strip()
]
# Deprecated: standing fleets are not classified by FC character ID.
SFT_KILL_BONUS_POINTS = _env_int("SFT_KILL_BONUS_POINTS", 5)
SFT_POINTS_PER_STANDING_HOUR = _env_float("SFT_POINTS_PER_STANDING_HOUR", 1.0)
SFT_PULSE_POINTS_PER_PULSE = _env_float("SFT_PULSE_POINTS_PER_PULSE", 0.25)
SFT_PENALTY_PER_SOV_ROAM_HOUR = _env_float("SFT_PENALTY_PER_SOV_ROAM_HOUR", 1.0)
SFT_SOV_CACHE_HOURS = _env_int("SFT_SOV_CACHE_HOURS", 6)
SFT_FIT_SNAPSHOT_RETENTION_DAYS = _env_int("SFT_FIT_SNAPSHOT_RETENTION_DAYS", 90)
SFT_WALLET_SCOPE = "esi-wallet.read_character_wallet.v1"
SFT_MINING_SCOPE = "esi-industry.read_character_mining.v1"
SFT_RATTING_REF_TYPES = [
    s.strip()
    for s in _env(
        "SFT_RATTING_REF_TYPES",
        "bounty_prizes,ess_escort_bounty,agent_mission_reward",
    ).split(",")
    if s.strip()
]
SFT_REQUIRED_SCOPES = _env(
    "SFT_REQUIRED_SCOPES",
    "esi-fleets.read_fleet.v1 esi-location.read_location.v1 esi-location.read_ship_type.v1 "
    "esi-assets.read_assets.v1 esi-killmails.read_killmails.v1",
).split()
