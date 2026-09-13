"""Map API schemas."""

from __future__ import annotations

from pydantic import BaseModel, Field


class JumpRouteRequest(BaseModel):
    origin: str | int
    destination: str | int
    ship_class: str | None = None
    ship_slug: str | None = None
    jump_drive_calibration: int = Field(default=0, ge=0, le=5)
    jump_fuel_conservation: int = Field(default=0, ge=0, le=5)
    jump_freighters: int = Field(default=0, ge=0, le=5)


class WhMapCreate(BaseModel):
    name: str
    creator_character_id: int
    creator_character_name: str = ""
    alliance_id: int | None = None


class WhSystemCreate(BaseModel):
    solar_system_id: int
    system_name: str = ""
    system_signature: str = ""
    wh_class: str = ""
    space_type: str = "j-space"
    effect: str = ""
    statics: list[str] = Field(default_factory=list)
    pos_x: float = 0.0
    pos_y: float = 0.0


class WhConnectionCreate(BaseModel):
    source_node_id: int
    target_node_id: int
    wh_type: str = ""
    mass_status: str = "normal"
    eol: bool = False
    signature_in: str = ""
    signature_out: str = ""


class WhConnectionPatch(BaseModel):
    mass_status: str | None = None
    eol: bool | None = None
    wh_type: str | None = None


class StateCreate(BaseModel):
    name: str
    priority_weight: int = 100
    color: str = "blue"
    description: str = ""


class StateRuleCreate(BaseModel):
    state_id: int
    allowed_alliance_ids: list[int] = Field(default_factory=list)
    allowed_corporation_ids: list[int] = Field(default_factory=list)
    priority: int = 100


class GroupCreate(BaseModel):
    name: str
    description: str = ""
    is_hidden: bool = False
    is_open: bool = False
    discord_role_id: str = ""
    permissions: list[str] = Field(default_factory=list)


class GroupUpdate(BaseModel):
    description: str | None = None
    is_hidden: bool | None = None
    is_open: bool | None = None
    discord_role_id: str | None = None
    permissions: list[str] | None = None
    active: bool | None = None


class StateRuleUpdate(BaseModel):
    allowed_alliance_ids: list[int] | None = None
    allowed_corporation_ids: list[int] | None = None
    priority: int | None = None


class GroupAssignRequest(BaseModel):
    character_id: int
    character_name: str = ""
    status: str = "active"


class GroupJoinRequest(BaseModel):
    character_id: int
    character_name: str = ""


class ServiceSyncConfigUpdate(BaseModel):
    discord_bot_token: str = ""
    discord_guild_id: str = ""
    discord_nickname_format: str = "[{ticker}] {name}"
    mumble_server_json: str = "{}"
    enabled: bool = False
