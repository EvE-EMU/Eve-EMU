"""Demo seed data for coalition tool suite."""

from __future__ import annotations

import json
from datetime import date, datetime, timedelta
from decimal import Decimal

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import settings
from app.services.structure_market_access import bootstrap_character_ids
from app.models import (
    AuditProfile,
    AuthedStructure,
    CorpMarketListing,
    FittingRecord,
    HrAccountFlag,
    HrBlacklistEntry,
    HrLeaveRequest,
    IndyHubJob,
    IndyBlueprint,
    IndyCopyRequest,
    IndyJobRecord,
    IndustryCalcJob,
    IndustrialBuildStructure,
    IndustrialProject,
    KillboardLeaderboard,
    MarketWatchItem,
    MaterialExchangeOrder,
    PniBill,
    PniStatement,
    ProjectJobCost,
    ProjectStockAssignment,
    RattingPayment,
    RattingTaxPeriod,
    RouteBookmark,
    SdeStargateLink,
    SdeSystem,
    SdeTypeIndex,
    ServiceLink,
    SrpLoss,
    SrpRateRule,
    StorefrontListing,
    BlueprintPublicContract,
)

COMMON_TYPES = [
    (34, "Tritanium", "Mineral", "Material", 0.01, 4.85),
    (35, "Pyerite", "Mineral", "Material", 0.01, 3.05),
    (36, "Mexallon", "Mineral", "Material", 0.01, 59.85),
    (37, "Isogen", "Mineral", "Material", 0.01, 355.85),
    (38, "Nocxium", "Mineral", "Material", 0.01, 812.85),
    (39, "Zydrine", "Mineral", "Material", 0.01, 1400.85),
    (40, "Megacyte", "Mineral", "Material", 0.01, 2800.85),
    (11399, "Morphite", "Mineral", "Material", 0.01, 8500.0),
    (16273, "Helium Isotopes", "Fuel Block", "Material", 0.25, 0),
    (16274, "Hydrogen Isotopes", "Fuel Block", "Material", 0.25, 0),
    (16275, "Nitrogen Isotopes", "Fuel Block", "Material", 0.25, 0),
    (16276, "Oxygen Isotopes", "Fuel Block", "Material", 0.25, 0),
    (17887, "Oxygen", "Planetary Commodities", "Material", 0.38, 0),
    (17888, "Heavy Water", "Planetary Commodities", "Material", 0.38, 0),
    (17889, "Liquid Ozone", "Planetary Commodities", "Material", 0.38, 0),
    (17890, "Helium", "Planetary Commodities", "Material", 0.38, 0),
    (17891, "Hydrogen", "Planetary Commodities", "Material", 0.38, 0),
    (17892, "Nitrogen", "Planetary Commodities", "Material", 0.38, 0),
    (626, "Veldspar", "Asteroid", "Material", 0.1, 0),
    (627, "Scordite", "Asteroid", "Material", 0.15, 0),
    (628, "Pyroxeres", "Asteroid", "Material", 0.15, 0),
    (629, "Plagioclase", "Asteroid", "Material", 0.15, 0),
    (630, "Omber", "Asteroid", "Material", 0.15, 0),
    (631, "Kernite", "Asteroid", "Material", 0.15, 0),
    (632, "Jaspet", "Asteroid", "Material", 0.15, 0),
    (633, "Hedbergite", "Asteroid", "Material", 0.15, 0),
    (634, "Hemorphite", "Asteroid", "Material", 0.15, 0),
    (635, "Gneiss", "Asteroid", "Material", 0.15, 0),
    (636, "Dark Ochre", "Asteroid", "Material", 0.15, 0),
    (637, "Spodumain", "Asteroid", "Material", 0.15, 0),
    (638, "Crokite", "Asteroid", "Material", 0.15, 0),
    (639, "Bistot", "Asteroid", "Material", 0.15, 0),
    (640, "Arkonor", "Asteroid", "Material", 0.15, 0),
    (641, "Mercoxit", "Asteroid", "Material", 0.15, 0),
    (587, "Rifter", "Frigate", "Ship", 27289.0, 0),
    (588, "Merlin", "Frigate", "Ship", 27289.0, 0),
    (589, "Punisher", "Frigate", "Ship", 27289.0, 0),
    (590, "Tormentor", "Frigate", "Ship", 27289.0, 0),
    (591, "Condor", "Frigate", "Ship", 27289.0, 0),
    (592, "Atron", "Frigate", "Ship", 27289.0, 0),
    (593, "Incursus", "Frigate", "Ship", 27289.0, 0),
    (594, "Imicus", "Frigate", "Ship", 27289.0, 0),
    (595, "Maulus", "Frigate", "Ship", 27289.0, 0),
    (596, "Crucifier", "Frigate", "Ship", 27289.0, 0),
    (597, "Heron", "Frigate", "Ship", 27289.0, 0),
    (598, "Probe", "Frigate", "Ship", 27289.0, 0),
    (599, "Magnate", "Frigate", "Ship", 27289.0, 0),
    (600, "Venture", "Frigate", "Ship", 27289.0, 0),
    (24688, "Tengu", "Strategic Cruiser", "Ship", 140000.0, 0),
    (24690, "Loki", "Strategic Cruiser", "Ship", 140000.0, 0),
    (24692, "Proteus", "Strategic Cruiser", "Ship", 140000.0, 0),
    (24694, "Legion", "Strategic Cruiser", "Ship", 140000.0, 0),
    (22448, "Hulk", "Exhumer", "Ship", 375000.0, 0),
    (22546, "Orca", "Industrial Command Ship", "Ship", 10000000.0, 0),
    (28659, "Rorqual", "Capital Industrial Ship", "Ship", 800000000.0, 0),
    (11987, "Guardian", "Logistics", "Ship", 115000.0, 0),
    (11989, "Basilisk", "Logistics", "Ship", 115000.0, 0),
    (11993, "Scimitar", "Logistics", "Ship", 115000.0, 0),
    (11995, "Oneiros", "Logistics", "Ship", 115000.0, 0),
    (56076, "Border-5 'Pochven' Filament", "Filament", "Deployable", 0.1, 0),
]


async def _ensure_common_types(session: AsyncSession) -> None:
    """Insert any COMMON_TYPES missing from an older seed."""
    existing_ids = set(
        (await session.scalars(select(SdeTypeIndex.type_id))).all()
    )
    for tid, name, group, cat, vol, price in COMMON_TYPES:
        if tid in existing_ids:
            continue
        session.add(
            SdeTypeIndex(
                type_id=tid,
                name=name,
                group_name=group,
                category_name=cat,
                volume_m3=vol,
                base_price=Decimal(str(price)),
            )
        )


async def seed_tools(session: AsyncSession) -> None:
    from app.services.sde_import import sde_types_is_loaded

    if await sde_types_is_loaded(session):
        await _seed_map_and_indy_if_empty(session)
    else:
        existing = await session.scalar(select(SdeTypeIndex).limit(1))
        if not existing:
            await _seed_types_and_core(session)
        else:
            await _seed_map_and_indy_if_empty(session)
            await _ensure_common_types(session)
    await _seed_industrial_planning_if_empty(session)
    await _repair_industrial_type_ids(session)
    await _ensure_demo_character_skills(session)


async def _ensure_demo_character_skills(session: AsyncSession) -> None:
    from app.models.character_skills import CharacterSkillLevel

    if await session.scalar(select(CharacterSkillLevel).limit(1)):
        return
    rows = [
        (2114756233, "Jo'Se", 3380, "Mining Frigate", 5),
        (2114756233, "Jo'Se", 3386, "Mining Barge", 4),
        (2114756233, "Jo'Se", 3416, "Astrogeology", 5),
        (2114756233, "Jo'Se", 3327, "Mining", 5),
        (2114756233, "Jo'Se", 3449, "Mining Upgrades", 4),
    ]
    if settings.seed_demo_data:
        rows.extend(
            [
                (90000001, "Demo Alt", 3380, "Mining Frigate", 3),
                (90000001, "Demo Alt", 3327, "Mining", 4),
                (90000001, "Demo Alt", 24624, "Spaceship Command", 5),
                (90000002, "Industry Alt", 24624, "Spaceship Command", 4),
                (90000002, "Industry Alt", 3387, "Industry", 5),
            ]
        )
    for cid, cname, sid, sname, lvl in rows:
        session.add(
            CharacterSkillLevel(
                character_id=cid,
                character_name=cname,
                skill_type_id=sid,
                skill_name=sname,
                trained_level=lvl,
            )
        )


# SDE blueprint type_ids (invTypes) — not product ship type_ids.
_BLUEPRINT_TYPE_IDS: dict[str, int] = {
    "Drake Blueprint": 24699,
    "Hulk Blueprint": 22545,
    "Tengu Blueprint": 29985,
}


async def _repair_industrial_type_ids(session: AsyncSession) -> None:
    """Fix demo rows that stored product type_ids instead of blueprint type_ids."""
    for name, type_id in _BLUEPRINT_TYPE_IDS.items():
        rows = (await session.scalars(select(IndyBlueprint).where(IndyBlueprint.type_name == name))).all()
        for row in rows:
            if row.type_id != type_id:
                row.type_id = type_id
    for row in (await session.scalars(select(StorefrontListing).where(StorefrontListing.type_name == "Tengu"))).all():
        if row.type_id != 29984:
            row.type_id = 29984


async def _seed_types_and_core(session: AsyncSession) -> None:
    for tid, name, group, cat, vol, price in COMMON_TYPES:
        session.add(
            SdeTypeIndex(
                type_id=tid,
                name=name,
                group_name=group,
                category_name=cat,
                volume_m3=vol,
                base_price=Decimal(str(price)),
            )
        )

    wompstar_owner = bootstrap_character_ids()[0] if bootstrap_character_ids() else 0
    session.add(
        AuthedStructure(
            structure_id=settings.wompstar_structure_id,
            structure_name=settings.wompstar_structure_name,
            system_name="3T7-M8",
            has_market=True,
            has_reprocessing=True,
            owner_character_id=wompstar_owner,
            solar_system_id=30004019,
        )
    )

    for svc in (
        ("discord", "WOMP Discord", "https://discord.gg/womp", "Voice, pings, and fleet coordination"),
        ("mumble", "WOMP Mumble", "mumble://mumble.eve-emu.com/WOMP", "Low-latency fleet comms"),
        ("wiki", "Industrial Wiki", "https://wiki.eve-emu.com", "SDE, doctrines, and corp knowledge base"),
    ):
        session.add(
            ServiceLink(service=svc[0], label=svc[1], url=svc[2], description=svc[3], requires_sso=svc[0] == "discord")
        )

    session.add(
        FittingRecord(
            name="WOMP T3 L4",
            ship_type_id=24688,
            ship_type_name="Tengu",
            doctrine_slug="womp-t3",
            eft_text="[Tengu, WOMP L4]\n...\n",
            tags_json=json.dumps(
                {
                    "tags": ["pve", "shield"],
                    "module_type_ids": [
                        12076,  # Adaptive Invulnerability Field II
                        41218,  # Assault Damage Control II
                        41220,  # Entropic Radiation Sink II
                        41212,  # Entropic Disintegrator II
                        1957,   # Multispectrum ECM Shield Hardener II
                        2281,   # Large Shield Extender II
                        2281,   # Large Shield Extender II
                        1405,   # Core Defense Field Extender II
                        26088,  # Core Defense Operational Solidifier II
                        26088,  # Core Defense Operational Solidifier II
                    ],
                }
            ),
        )
    )
    session.add(
        FittingRecord(
            name="WOMP Hulk Mining",
            ship_type_id=22448,
            ship_type_name="Hulk",
            doctrine_slug="womp-mining",
            eft_text="[Hulk, WOMP Mining]\n...\n",
            tags_json=json.dumps(
                {
                    "tags": ["mining"],
                    "module_type_ids": [
                        28756,  # Modulated Strip Miner II
                        28756,
                        4383,   # Mining Laser Upgrade II
                        4383,
                        4383,
                        1952,   # Multispectrum Shield Hardener II
                        2281,   # Large Shield Extender II
                    ],
                }
            ),
        )
    )

    session.add(
        SrpRateRule(
            label="Tengu WOMP doctrine",
            ship_type_id=24688,
            ship_type_name="Tengu",
            doctrine_slug="womp-t3",
            base_srp_isk=Decimal("680000000"),
            max_percent=Decimal("80"),
            doctrine_multiplier=Decimal("1"),
            meta_multiplier=Decimal("0.75"),
            shitfit_multiplier=Decimal("0"),
            allow_shitfit=False,
            enabled=True,
            priority=200,
        )
    )
    session.add(
        SrpRateRule(
            label="Hulk mining",
            ship_type_id=22448,
            ship_type_name="Hulk",
            doctrine_slug="womp-mining",
            base_srp_isk=Decimal("450000000"),
            max_percent=Decimal("90"),
            doctrine_multiplier=Decimal("1"),
            meta_multiplier=Decimal("0.8"),
            shitfit_multiplier=Decimal("0"),
            allow_shitfit=False,
            enabled=True,
            priority=150,
        )
    )
    session.add(
        SrpRateRule(
            label="Default hull SRP",
            ship_type_id=0,
            ship_type_name="Any",
            doctrine_slug="",
            base_srp_isk=Decimal("200000000"),
            max_percent=Decimal("60"),
            doctrine_multiplier=Decimal("1"),
            meta_multiplier=Decimal("0.5"),
            shitfit_multiplier=Decimal("0"),
            allow_shitfit=False,
            enabled=True,
            priority=10,
        )
    )

    if settings.seed_demo_data:
        session.add(
            AuditProfile(
                character_id=2115759417,
                character_name="Solomon Iskander",
                corporation_name="False Gods",
                wallet_balance_isk=Decimal("12500000000"),
                skill_points=85000000,
                assets_value_isk=Decimal("45000000000"),
                snapshot_json=json.dumps({"skills_trained": 142, "alts_linked": 4}),
            )
        )

        period = RattingTaxPeriod(
            period_label="June 2026",
            rate_pct=Decimal("10"),
            total_bounty_isk=Decimal("85000000000"),
            total_collected_isk=Decimal("6200000000"),
        )
        session.add(period)
        await session.flush()
        session.add(
            RattingPayment(
                period_id=period.id,
                character_name="Solomon Iskander",
                bounty_isk=Decimal("2400000000"),
                tax_due_isk=Decimal("240000000"),
                paid_isk=Decimal("240000000"),
                status="paid",
            )
        )

        session.add(
            KillboardLeaderboard(
                scope="alliance",
                scope_id=settings.killboard_alliance_id,
                character_id=2115759417,
                character_name="Solomon Iskander",
                kills=42,
                losses=8,
                isk_destroyed=Decimal("8500000000"),
                isk_lost=Decimal("1200000000"),
            )
        )
        session.add(
            KillboardLeaderboard(
                scope="alliance",
                scope_id=settings.killboard_alliance_id,
                character_id=715529239,
                character_name="sevey",
                kills=38,
                losses=12,
                isk_destroyed=Decimal("7200000000"),
                isk_lost=Decimal("2100000000"),
            )
        )

        stmt = PniStatement(
            period_label="Q2 2026",
            status="open",
            total_income_isk=Decimal("125000000000"),
            total_expense_isk=Decimal("98000000000"),
            payload_json=json.dumps({"categories": ["moon_tax", "ratting", "industry"]}),
        )
        session.add(stmt)
        await session.flush()
        session.add(
            PniBill(
                statement_id=stmt.id,
                bill_type="structure_fuel",
                description="Structure fuel block purchase",
                amount_isk=Decimal("4500000000"),
                status="open",
                due_at=date.today() + timedelta(days=14),
            )
        )

        session.add(
            MarketWatchItem(
                type_id=34,
                type_name="Tritanium",
                location_label="Jita",
                best_buy=Decimal("4.50"),
                best_sell=Decimal("4.85"),
                spread_pct=7.8,
            )
        )

        session.add(
            SrpLoss(
                killmail_id=123456789,
                killmail_hash="demo0000000000000000000000000000000000",
                character_id=2115759417,
                character_name="Solomon Iskander",
                ship_type_id=24688,
                ship_type_name="Tengu",
                total_value_isk=Decimal("850000000"),
                srp_amount_isk=Decimal("680000000"),
                fit_grade="doctrine",
                doctrine_slug="womp-t3",
                doctrine_match_pct=92.0,
                fit_json="[]",
                status="pending",
                zkill_url="https://zkillboard.com/kill/123456789/",
            )
        )

    session.add(
        RouteBookmark(
            name="Jita → Holy Procurer",
            origin_system="Jita",
            destination_system="3T7-M8",
            origin_system_id=30000142,
            destination_system_id=30002938,
            jumps=12,
            route_json=json.dumps(["Jita", "Perimeter", "New Caldari", "…", "3T7-M8"]),
            security_max=0.9,
            route_mode="stargate",
            visibility="corp",
        )
    )

    session.add(
        IndustryCalcJob(
            blueprint_name="Tritanium Reaction",
            runs=10,
            material_cost_isk=Decimal("450000000"),
            product_value_isk=Decimal("520000000"),
            profit_isk=Decimal("70000000"),
        )
    )

    session.add(
        CorpMarketListing(
            seller_character_name="Solomon Iskander",
            type_id=34,
            type_name="Tritanium",
            quantity=50000000,
            unit_price_isk=Decimal("4.75"),
            listing_type="sell",
            structure_name=settings.wompstar_structure_name,
        )
    )

    session.add(
        IndyHubJob(
            job_type="manufacturing",
            requester="sevey",
            blueprint_name="Drake",
            status="in_progress",
            runs=5,
            due_at=date.today() + timedelta(days=3),
        )
    )

    session.add(
        HrLeaveRequest(
            character_name="Solomon Iskander",
            character_id=2115759417,
            start_date=date.today() + timedelta(days=7),
            end_date=date.today() + timedelta(days=21),
            reason="Real life deployment",
            status="approved",
        )
    )
    session.add(
        HrBlacklistEntry(
            character_name="Example Scammer",
            reason="Contract scam — do not recruit",
            added_by="HR Directorate",
        )
    )
    session.add(
        HrAccountFlag(
            target_character_id=2115759417,
            target_character_name="Solomon Iskander",
            flag_key="director",
            flag_label="Director",
            color="ok",
            notes="Industrial directorate access",
        )
    )

    await _seed_map_and_indy(session)


async def _seed_map_and_indy_if_empty(session: AsyncSession) -> None:
    from pathlib import Path

    from app.config import settings
    from app.services.sde_import import sde_map_is_loaded

    if await sde_map_is_loaded(session):
        return
    if Path(settings.sde_sqlite_path).is_file():
        return
    if await session.scalar(select(SdeSystem).limit(1)):
        return
    await _seed_map_and_indy(session)


async def _seed_map_and_indy(session: AsyncSession) -> None:
    """Seed stargate graph, Indy Hub demo data (runs even when types already exist)."""
    systems = [
        (30000142, "Jita", 0.945, "The Forge", "Kimotoro"),
        (30000144, "Perimeter", 1.0, "The Forge", "Kimotoro"),
        (30000145, "New Caldari", 0.789, "The Forge", "Kimotoro"),
        (30000138, "Ikuchi", 0.812, "The Forge", "Okkoken"),
        (30001363, "Sobaseki", 0.838, "The Forge", "Okkoken"),
        (30002938, "3T7-M8", -0.59, "Deklein", "RFY-QB"),
        (30002187, "1-SMEB", -0.28, "Delve", "YZ9-F6"),
        (30002188, "F-TE1T", -0.35, "Delve", "YZ9-F6"),
        (30002189, "H-ADOC", -0.42, "Delve", "YZ9-F6"),
        (30002190, "M-SRKS", -0.38, "Delve", "YZ9-F6"),
        (30002191, "O3L-95", -0.31, "Delve", "YZ9-F6"),
        (30002192, "P-ZMZ3", -0.29, "Delve", "YZ9-F6"),
        (30002193, "Q-HESZ", -0.33, "Delve", "YZ9-F6"),
        (30002194, "S-RPJH", -0.36, "Delve", "YZ9-F6"),
        (30002195, "T-IPZB", -0.40, "Delve", "YZ9-F6"),
        (30002196, "U-JTBT", -0.44, "Delve", "YZ9-F6"),
        (30002197, "V-3YG7", -0.47, "Delve", "YZ9-F6"),
        (30002198, "W-4NUU", -0.41, "Delve", "YZ9-F6"),
        (30002199, "X-7OMU", -0.39, "Delve", "YZ9-F6"),
        (30002200, "Y-MPWL", -0.37, "Delve", "YZ9-F6"),
        (30002201, "Z-6YQC", -0.43, "Delve", "YZ9-F6"),
        (30002202, "0-VG7A", -0.46, "Delve", "YZ9-F6"),
        (30002203, "1-2HWZ", -0.48, "Delve", "YZ9-F6"),
        (30002204, "2-TEGJ", -0.50, "Delve", "YZ9-F6"),
        (30002205, "3-LJW3", -0.52, "Delve", "YZ9-F6"),
        (30002206, "4-OUKF", -0.49, "Delve", "YZ9-F6"),
        (30002207, "5-FCZP", -0.51, "Delve", "YZ9-F6"),
        (30002208, "6-CZ49", -0.53, "Delve", "YZ9-F6"),
        (30002209, "7-8EOE", -0.55, "Delve", "YZ9-F6"),
        (30002210, "8-KEAF", -0.54, "Delve", "YZ9-F6"),
        (30002211, "9-266Q", -0.56, "Delve", "YZ9-F6"),
        (30002212, "A-REKV", -0.57, "Delve", "YZ9-F6"),
        (30002213, "B-DBYQ", -0.58, "Delve", "YZ9-F6"),
        (30002214, "C-J6MT", -0.59, "Delve", "YZ9-F6"),
        (30002215, "D-6PKO", -0.60, "Delve", "YZ9-F6"),
        (30002216, "E-3LYO", -0.61, "Delve", "YZ9-F6"),
        (30002217, "F-9PXR", -0.62, "Delve", "YZ9-F6"),
        (30002218, "G-0Q86", -0.63, "Delve", "YZ9-F6"),
        (30002219, "H-PA29", -0.64, "Delve", "YZ9-F6"),
        (30002220, "I-1QKL", -0.65, "Delve", "YZ9-F6"),
        (30002221, "J-RXYN", -0.66, "Delve", "YZ9-F6"),
        (30002222, "K-6K16", -0.67, "Delve", "YZ9-F6"),
        (30002223, "L-5M4P", -0.68, "Delve", "YZ9-F6"),
        (30002224, "M-75C9", -0.69, "Delve", "YZ9-F6"),
        (30002225, "N-8YET", -0.70, "Delve", "YZ9-F6"),
        (30002226, "O-BDXB", -0.71, "Delve", "YZ9-F6"),
        (30002227, "P-FSQE", -0.72, "Delve", "YZ9-F6"),
        (30002228, "Q-NAWH", -0.73, "Delve", "YZ9-F6"),
        (30002229, "R-AGHW", -0.74, "Delve", "YZ9-F6"),
        (30002230, "S-MDYI", -0.75, "Delve", "YZ9-F6"),
        (30002231, "T-IPZB", -0.40, "Delve", "YZ9-F6"),
    ]
    # Deduplicate by system_id (T-IPZB listed twice in demo graph)
    seen: set[int] = set()
    for sid, name, sec, region, const in systems:
        if sid in seen:
            continue
        seen.add(sid)
        session.add(
            SdeSystem(
                system_id=sid,
                name=name,
                security=sec,
                region_name=region,
                constellation_name=const,
            )
        )

    # Compact trade route + delve pocket mesh
    edges = [
        (30000142, 30000144),
        (30000144, 30000145),
        (30000145, 30000138),
        (30000138, 30001363),
        (30001363, 30004019),
        (30004019, 30002187),
        (30002187, 30002188),
        (30002188, 30002189),
        (30002189, 30002190),
        (30002190, 30002191),
        (30002191, 30002192),
        (30002192, 30002193),
        (30002193, 30002194),
        (30002194, 30002195),
        (30002195, 30002196),
        (30002196, 30002197),
        (30002197, 30002198),
        (30002198, 30002199),
        (30002199, 30002200),
        (30002200, 30002201),
        (30002201, 30002202),
        (30002202, 30002203),
        (30004019, 30002231),
        (30002231, 30002195),
    ]
    for a, b in edges:
        session.add(SdeStargateLink(from_system_id=a, to_system_id=b))

    from app.services.map_layout import apply_map_layout

    await apply_map_layout(session)

    session.add(
        IndyBlueprint(
            owner_character_name="Solomon Iskander",
            owner_scope="personal",
            type_id=24699,
            type_name="Drake Blueprint",
            material_efficiency=10,
            time_efficiency=20,
            runs=-1,
            location_name="Jita 4-4",
            shared=True,
            copy_available=True,
        )
    )
    session.add(
        IndyBlueprint(
            owner_character_name="False Gods",
            owner_scope="corp",
            type_id=22545,
            type_name="Hulk Blueprint",
            material_efficiency=5,
            time_efficiency=10,
            runs=8,
            location_name=settings.wompstar_structure_name,
            shared=True,
            copy_available=True,
        )
    )
    session.add(
        IndyBlueprint(
            owner_character_name="sevey",
            owner_scope="personal",
            type_id=29985,
            type_name="Tengu Blueprint",
            material_efficiency=8,
            time_efficiency=14,
            runs=3,
            location_name=settings.wompstar_structure_name,
            shared=False,
            copy_available=True,
        )
    )

    session.add(
        IndyJobRecord(
            character_name="sevey",
            blueprint_name="Drake",
            activity="manufacturing",
            runs=5,
            status="active",
            location_name=settings.wompstar_structure_name,
            ends_at=datetime.now() + timedelta(days=3),
            output_type_name="Drake",
        )
    )
    session.add(
        IndyJobRecord(
            character_name="Solomon Iskander",
            blueprint_name="Hulk",
            activity="research",
            runs=1,
            status="active",
            location_name="Jita 4-4",
            ends_at=datetime.now() + timedelta(days=1),
            output_type_name="Hulk Blueprint",
        )
    )
    session.add(
        IndyJobRecord(
            character_name="sevey",
            blueprint_name="Tengu",
            activity="invention",
            runs=10,
            status="completed",
            location_name=settings.wompstar_structure_name,
            ends_at=datetime.now() - timedelta(days=2),
            output_type_name="Tengu Prototype",
        )
    )

    session.add(
        IndyCopyRequest(
            requester="Solomon Iskander",
            blueprint_name="Raven",
            runs=5,
            status="open",
            delivery_location="Jita 4-4",
            notes="Need for incursion fleet",
        )
    )
    session.add(
        IndyCopyRequest(
            requester="sevey",
            blueprint_name="Orca",
            runs=1,
            status="offered",
            assignee="Solomon Iskander",
            delivery_location=settings.wompstar_structure_name,
            notes="Corp logistics project",
        )
    )
    session.add(
        IndyCopyRequest(
            requester="Example Pilot",
            blueprint_name="Ishtar",
            runs=3,
            status="delivered",
            assignee="sevey",
            delivery_location="3T7-M8",
            notes="Delivered via contract",
        )
    )

    session.add(
        MaterialExchangeOrder(
            character_name="Solomon Iskander",
            type_id=34,
            type_name="Tritanium",
            side="sell",
            quantity=50000000,
            unit_price_isk=Decimal("4.75"),
            status="pending",
        )
    )
    session.add(
        MaterialExchangeOrder(
            character_name="sevey",
            type_id=35,
            type_name="Pyerite",
            side="buy",
            quantity=10000000,
            unit_price_isk=Decimal("3.10"),
            status="processing",
        )
    )
    session.add(
        MaterialExchangeOrder(
            character_name="Example Pilot",
            type_id=37,
            type_name="Isogen",
            side="sell",
            quantity=500000,
            unit_price_isk=Decimal("350.00"),
            status="completed",
        )
    )


async def _seed_industrial_planning_if_empty(session: AsyncSession) -> None:
    if await session.scalar(select(IndustrialBuildStructure).limit(1)):
        return

    session.add(
        IndustrialBuildStructure(
            structure_id=settings.wompstar_structure_id,
            structure_name=settings.wompstar_structure_name,
            system_name="3T7-M8",
            location_label="WOMP Stock",
            material_bonus_pct=4.2,
            time_bonus_pct=20.0,
            tax_pct=1.0,
        )
    )
    session.add(
        IndustrialBuildStructure(
            structure_id=60003760,
            structure_name="Jita 4-4 Caldari Navy Assembly Plant",
            system_name="Jita",
            location_label="Jita Hub",
            material_bonus_pct=0.0,
            time_bonus_pct=0.0,
            tax_pct=2.5,
        )
    )
    session.add(
        IndustrialBuildStructure(
            structure_id=60008494,
            structure_name="Amarr VIII - Emperor Family Academy",
            system_name="Amarr",
            location_label="Amarr Stock",
            material_bonus_pct=1.0,
            time_bonus_pct=2.0,
            tax_pct=2.5,
        )
    )

    project = IndustrialProject(
        project_code="PROJ-WOMP1",
        name="T3 Batch — June",
        container_name="IP-WOMP-T3-Container",
        owner_character_name="sevey",
        status="active",
        notes="True-cost tracking for coalition T3 run",
    )
    session.add(project)
    await session.flush()

    session.add(
        ProjectStockAssignment(
            project_id=project.id,
            type_id=34,
            type_name="Tritanium",
            quantity=12000000,
            unit_cost_isk=Decimal("4.75"),
            container_name="IP-WOMP-T3-Container",
        )
    )
    session.add(
        ProjectStockAssignment(
            project_id=project.id,
            type_id=35,
            type_name="Pyerite",
            quantity=4500000,
            unit_cost_isk=Decimal("3.10"),
            container_name="IP-WOMP-T3-Container",
        )
    )
    session.add(
        ProjectJobCost(
            project_id=project.id,
            description="Tengu hull manufacturing",
            activity="manufacturing",
            runs=5,
            cost_isk=Decimal("125000000"),
            structure_name=settings.wompstar_structure_name,
        )
    )

    session.add(
        BlueprintPublicContract(
            contract_id=987654321,
            blueprint_name="Raven Blueprint",
            seller_name="Jita Industrial Ltd",
            location="Jita 4-4",
            price_isk=Decimal("85000000"),
            runs=10,
            material_efficiency=8,
            time_efficiency=12,
        )
    )
    session.add(
        BlueprintPublicContract(
            contract_id=987654322,
            blueprint_name="Orca Blueprint",
            seller_name="Solomon Iskander",
            location=settings.wompstar_structure_name,
            price_isk=Decimal("420000000"),
            runs=1,
            material_efficiency=5,
            time_efficiency=10,
        )
    )

    session.add(
        StorefrontListing(
            seller_character_name="sevey",
            type_id=29984,
            type_name="Tengu",
            quantity=3,
            suggested_price_isk=Decimal("195000000"),
            price_public_isk=Decimal("210000000"),
            price_corp_isk=Decimal("198000000"),
            price_alliance_isk=Decimal("192000000"),
            pricing_mode="standings",
            visibility="public",
            price_basis="alliance_recent",
        )
    )
    session.add(
        StorefrontListing(
            seller_character_name="Solomon Iskander",
            type_id=34,
            type_name="Tritanium",
            quantity=25000000,
            suggested_price_isk=Decimal("4.72"),
            price_public_isk=Decimal("4.85"),
            price_corp_isk=Decimal("4.70"),
            price_alliance_isk=Decimal("4.68"),
            pricing_mode="corp",
            visibility="alliance",
            price_basis="corp_market",
        )
    )
