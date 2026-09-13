"""Pydantic schemas for coalition tools."""

from __future__ import annotations

from datetime import date, datetime
from decimal import Decimal

from pydantic import BaseModel, Field


class AppraisalRequest(BaseModel):
    text: str
    sell_market: str = "jita"
    buy_market: str | None = None


class BuybackRequest(BaseModel):
    text: str
    fee_pct: float | None = None
    sell_market: str = "jita"
    item_location: str | None = None


class CorpMarketOrderCreate(BaseModel):
    buyer_character_name: str
    buyer_character_id: int | None = None
    type_id: int | None = None
    type_name: str = ""
    quantity: int = Field(ge=1)
    unit_price_isk: float = Field(gt=0)
    delivery_location: str
    notes: str = ""


class CorpMarketOrderOut(BaseModel):
    id: int
    status: str
    type_id: int
    type_name: str
    quantity: int
    unit_price_isk: float
    total_price_isk: float
    delivery_location: str
    mail_sent_buyer: bool = False
    mail_sent_corp: bool = False
    mail_error: str | None = None


class BuybackLocationOut(BaseModel):
    id: str
    label: str
    fee_pct: float
    market: str


class AppraisalLineOut(BaseModel):
    type_id: int | None = None
    name: str
    quantity: int
    single_sell: float | None = None
    single_buy: float | None = None
    total_sell: float | None = None
    total_buy: float | None = None


class AppraisalOut(BaseModel):
    id: int | None = None
    share_token: str | None = None
    share_url: str | None = None
    sell_market: str
    buy_market: str
    sell_market_label: str
    buy_market_label: str
    janice_configured: bool
    totals: dict
    unresolved: list[str] = Field(default_factory=list)
    lines: list[dict] = Field(default_factory=list)
    fee_pct: float | None = None
    contract_value_isk: float | None = None
    fee_basis_isk: float | None = None
    item_location: str | None = None
    item_location_label: str | None = None
    contract_code: str | None = None
    contract_description: str | None = None
    janice_code: str | None = None
    janice_url: str | None = None
    buyback_locations: list[dict] = Field(default_factory=list)


class SdeTypeOut(BaseModel):
    type_id: int
    name: str
    group_name: str
    category_name: str
    volume_m3: float
    base_price: float

    model_config = {"from_attributes": True}


class SdeTypeAttributeOut(BaseModel):
    attribute_id: int
    name: str
    value: float
    description: str = ""


class SdeTypeRequirementOut(BaseModel):
    kind: str
    type_id: int | None = None
    name: str
    level: int | None = None


class SdeSkillMetaOut(BaseModel):
    rank: int = 0
    primary_attribute: str = ""
    secondary_attribute: str = ""


class SdeTypeSkillCheckOut(BaseModel):
    can_use: bool
    missing: list[dict] = Field(default_factory=list)


class SdeIndustryMaterialOut(BaseModel):
    type_id: int
    name: str
    quantity: int


class SdeIndustryRecipeOut(BaseModel):
    activity: str
    blueprint_type_id: int
    blueprint_name: str
    product_quantity: int
    materials: list[SdeIndustryMaterialOut]


class SdeStorefrontRefOut(BaseModel):
    id: int
    type_id: int
    type_name: str
    quantity: int
    price_public_isk: float
    suggested_price_isk: float


class SdeTypeDetailOut(BaseModel):
    type_id: int
    name: str
    group_name: str
    category_name: str
    group_id: int | None = None
    description: str
    published: bool = True
    mass: float = 0
    volume_m3: float = 0
    capacity: float = 0
    base_price: float = 0
    attributes: list[SdeTypeAttributeOut]
    requirements: list[SdeTypeRequirementOut]
    industry: list[SdeIndustryRecipeOut]
    storefront_listing: SdeStorefrontRefOut | None = None
    skill_meta: SdeSkillMetaOut | None = None
    skill_check: SdeTypeSkillCheckOut | None = None


class SdeCompareOut(BaseModel):
    type_ids: list[int]
    items: list[dict]
    attributes: list[dict]
    requirements: list[dict]


class SdeSkillCheckBatchIn(BaseModel):
    type_ids: list[int] = Field(default_factory=list)


class SdeCompareIn(BaseModel):
    type_ids: list[int] = Field(default_factory=list)


class AuthedStructureOut(BaseModel):
    structure_id: int
    structure_name: str
    system_name: str
    has_market: bool
    has_reprocessing: bool

    model_config = {"from_attributes": True}


class ServiceLinkOut(BaseModel):
    id: int
    service: str
    label: str
    url: str
    description: str
    requires_sso: bool
    active: bool

    model_config = {"from_attributes": True}


class AuditProfileOut(BaseModel):
    character_id: int
    character_name: str
    corporation_name: str
    wallet_balance_isk: Decimal
    skill_points: int
    assets_value_isk: Decimal
    snapshot_json: str

    model_config = {"from_attributes": True}


class FittingOut(BaseModel):
    id: int
    name: str
    ship_type_id: int
    ship_type_name: str
    doctrine_slug: str
    eft_text: str
    tags_json: str
    owner_character_id: int | None = None
    owner_character_name: str = ""

    model_config = {"from_attributes": True}


class KillboardRowOut(BaseModel):
    character_id: int
    character_name: str
    kills: int
    losses: int
    isk_destroyed: Decimal
    isk_lost: Decimal

    model_config = {"from_attributes": True}


class KillboardAttackerOut(BaseModel):
    character_id: int | None = None
    character_name: str | None = None
    damage_done: int = 0
    final_blow: bool = False


class RecentKillOut(BaseModel):
    killmail_id: int
    killmail_hash: str = ""
    killed_at: str | None = None
    outcome: str
    solar_system_id: int | None = None
    solar_system_name: str | None = None
    ship_type_id: int | None = None
    ship_type_name: str | None = None
    total_value: float = 0
    pilot_character_id: int | None = None
    pilot_character_name: str | None = None
    victim_character_id: int | None = None
    victim_character_name: str | None = None
    attackers: list[KillboardAttackerOut] = []
    zkill_url: str = ""
    source: str = "zkill"


class KillboardPilotOut(BaseModel):
    character_id: int
    character_name: str
    kills: int
    losses: int
    isk_destroyed: float
    isk_lost: float
    recent_kills: list[RecentKillOut] = []
    in_roster: bool = False
    zkill_url: str = ""


class HrLeaveOut(BaseModel):
    id: int
    character_name: str
    start_date: date
    end_date: date
    reason: str
    status: str

    model_config = {"from_attributes": True}


class HrLeaveCreate(BaseModel):
    character_name: str
    character_id: int = 0
    start_date: date
    end_date: date
    reason: str = ""


class RattingPeriodOut(BaseModel):
    id: int
    period_label: str
    rate_pct: Decimal
    status: str
    total_bounty_isk: Decimal
    total_collected_isk: Decimal

    model_config = {"from_attributes": True}


class SrpLossOut(BaseModel):
    id: int
    killmail_id: int
    killmail_hash: str = ""
    character_id: int = 0
    character_name: str
    ship_type_id: int = 0
    ship_type_name: str
    total_value_isk: Decimal
    srp_amount_isk: Decimal
    fit_grade: str = "shitfit"
    doctrine_slug: str = ""
    doctrine_match_pct: float = 0.0
    status: str
    zkill_url: str
    solar_system_name: str = ""
    killed_at: datetime | None = None
    submitted_at: datetime | None = None
    submitted_notes: str = ""

    model_config = {"from_attributes": True}


class MarketWatchOut(BaseModel):
    type_id: int
    type_name: str
    location_label: str
    best_buy: Decimal | None
    best_sell: Decimal | None
    spread_pct: float | None

    model_config = {"from_attributes": True}


class CorpMarketListingOut(BaseModel):
    id: int
    seller_character_name: str
    type_id: int
    type_name: str
    quantity: int
    unit_price_isk: Decimal
    listing_type: str
    status: str
    structure_name: str

    model_config = {"from_attributes": True}


class IndyHubJobOut(BaseModel):
    id: int
    job_type: str
    requester: str
    blueprint_name: str
    status: str
    runs: int
    due_at: date | None

    model_config = {"from_attributes": True}


class RouteBookmarkOut(BaseModel):
    id: int
    name: str
    origin_system: str
    destination_system: str
    origin_system_id: int | None = None
    destination_system_id: int | None = None
    jumps: int
    security_max: float
    route_mode: str = "stargate"
    visibility: str = "personal"
    owner_character_id: int | None = None
    owner_character_name: str = ""
    waypoint_system_ids: list[int] = Field(default_factory=list)
    route_json: list[str] = Field(default_factory=list)
    payload: dict = Field(default_factory=dict)
    share_token: str | None = None
    share_url: str | None = None
    created_at: str | None = None

    model_config = {"from_attributes": True}


class RouteBookmarkCreate(BaseModel):
    name: str
    origin_system: str
    destination_system: str
    origin_system_id: int | None = None
    destination_system_id: int | None = None
    jumps: int = 0
    route_mode: str = "stargate"
    visibility: str = Field(default="personal", pattern="^(personal|corp|alliance|link)$")
    security_max: float = 1.0
    route_names: list[str] = Field(default_factory=list)
    waypoint_system_ids: list[int] = Field(default_factory=list)
    payload: dict = Field(default_factory=dict)
    owner_character_id: int | None = None
    owner_character_name: str = ""
    corporation_id: int | None = None
    alliance_id: int | None = None


class IndustryCalcOut(BaseModel):
    id: int
    blueprint_name: str
    runs: int
    material_cost_isk: Decimal
    product_value_isk: Decimal
    profit_isk: Decimal

    model_config = {"from_attributes": True}


class PniStatementOut(BaseModel):
    id: int
    period_label: str
    status: str
    total_income_isk: Decimal
    total_expense_isk: Decimal

    model_config = {"from_attributes": True}


class SdeSystemOut(BaseModel):
    system_id: int
    name: str
    security: float
    region_name: str
    constellation_name: str = ""
    x: float | None = None
    y: float | None = None

    model_config = {"from_attributes": True}


class IndyBlueprintOut(BaseModel):
    id: int
    owner_character_name: str
    owner_character_id: int | None = None
    owner_scope: str
    type_id: int
    type_name: str
    material_efficiency: int
    time_efficiency: int
    runs: int
    location_name: str
    shared: bool
    copy_available: bool

    model_config = {"from_attributes": True}


class IndyJobRecordOut(BaseModel):
    id: int
    character_name: str
    owner_character_id: int | None = None
    installer_id: int | None = None
    installer_name: str = ""
    job_id: int | None = None
    blueprint_name: str
    activity: str
    runs: int
    status: str
    location_name: str
    facility_id: int | None = None
    started_at: datetime | None = None
    ends_at: datetime | None = None
    output_type_name: str

    model_config = {"from_attributes": True}


class CharacterMarketOrderOut(BaseModel):
    id: int
    character_id: int
    character_name: str
    order_id: int
    type_id: int
    type_name: str
    is_buy_order: bool
    price: Decimal
    volume_remain: int
    volume_total: int
    min_volume: int
    location_id: int
    location_name: str
    range_label: str
    issued_at: datetime | None
    duration_days: int
    is_corporation: bool

    model_config = {"from_attributes": True}


class IndyCopyRequestOut(BaseModel):
    id: int
    requester: str
    blueprint_name: str
    runs: int
    status: str
    assignee: str
    delivery_location: str
    notes: str
    created_at: datetime

    model_config = {"from_attributes": True}


class MaterialExchangeOrderOut(BaseModel):
    id: int
    character_name: str
    type_id: int
    type_name: str
    side: str
    quantity: int
    unit_price_isk: Decimal
    status: str
    created_at: datetime

    model_config = {"from_attributes": True}


class RoutePlanRequest(BaseModel):
    origin_system_id: int
    destination_system_id: int
    max_security: float = 1.0
    avoid_low_sec: bool = False
    waypoint_system_ids: list[int] = Field(default_factory=list)


class MapActivityRequest(BaseModel):
    system_ids: list[int] = Field(default_factory=list, max_length=200)


class JumpRangeRequest(BaseModel):
    origin_system_id: int
    jump_range: int = 5
    max_security: float = 1.0


class JumpPlanRequest(BaseModel):
    ship_slug: str
    origin_system_id: int
    destination_system_id: int
    jump_drive_calibration: int = Field(default=0, ge=0, le=5)
    jump_fuel_conservation: int = Field(default=0, ge=0, le=5)
    jump_freighters: int = Field(default=0, ge=0, le=5)


class JumpRangeDriveRequest(BaseModel):
    ship_slug: str
    origin_system_id: int
    jump_drive_calibration: int = Field(default=0, ge=0, le=5)


class IndustrialPlanRequest(BaseModel):
    source_type: str  # fitting|blueprint|product
    source_id: int
    location_filter: str = "all"  # all|stock|station
    station_name: str | None = None
    structure_id: int | None = None
    runs: int = Field(default=1, ge=1, le=10000)
    material_mode: str = "base"  # base|components
    price_hub: str = "jita"
    price_overrides: dict[int, Decimal] = Field(default_factory=dict)
    stock_assignments: dict[int, int] = Field(default_factory=dict)
    stock_location_ids: list[int] = Field(default_factory=list)
    use_max_stock: bool = True
    project_id: int | None = None
    container_name: str | None = None


class FittingCreateRequest(BaseModel):
    name: str = Field(min_length=1, max_length=256)
    ship_type_id: int = Field(gt=0)
    eft_text: str = ""


class BuildStructureIn(BaseModel):
    structure_id: int = Field(gt=0)
    structure_name: str = Field(min_length=1, max_length=256)
    system_name: str = Field(default="", max_length=128)
    location_label: str = Field(default="", max_length=128)
    material_bonus_pct: float = Field(default=0.0, ge=0, le=50)
    time_bonus_pct: float = Field(default=0.0, ge=0, le=50)
    tax_pct: float = Field(default=0.0, ge=0, le=25)
    has_manufacturing: bool = True


class BuildStructurePatch(BaseModel):
    structure_name: str | None = Field(default=None, max_length=256)
    system_name: str | None = Field(default=None, max_length=128)
    location_label: str | None = Field(default=None, max_length=128)
    material_bonus_pct: float | None = Field(default=None, ge=0, le=50)
    time_bonus_pct: float | None = Field(default=None, ge=0, le=50)
    tax_pct: float | None = Field(default=None, ge=0, le=25)
    has_manufacturing: bool | None = None


class IndustrialProjectCreate(BaseModel):
    name: str
    container_name: str
    owner_character_name: str = "Pilot"
    notes: str = ""


class BlueprintContractOut(BaseModel):
    id: int
    contract_id: int
    blueprint_name: str
    seller_name: str
    location: str
    price_isk: Decimal
    runs: int
    material_efficiency: int
    time_efficiency: int

    model_config = {"from_attributes": True}


class StorefrontListingOut(BaseModel):
    id: int
    seller_character_name: str
    type_id: int
    type_name: str
    quantity: int
    suggested_price_isk: Decimal
    price_public_isk: Decimal
    price_corp_isk: Decimal
    price_alliance_isk: Decimal
    pricing_mode: str
    visibility: str
    price_basis: str

    model_config = {"from_attributes": True}


class ToolsHubOut(BaseModel):
    categories: list[dict]
    authed_structures: list[AuthedStructureOut]
    markets: list[str]


class MarketBrowserOrdersQuery(BaseModel):
    kind: str = Field(description="region | station | structure")
    location_id: int
    type_id: int
    region_id: int | None = None
    order_type: str = "all"
