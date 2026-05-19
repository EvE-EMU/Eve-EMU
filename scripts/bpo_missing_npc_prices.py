#!/usr/bin/env python3
"""Compare owned BPO names to Fuzzwork SDE NPC seed prices (basePrice)."""

from __future__ import annotations

import bz2
import csv
import io
import urllib.request

FUZZWORK = "https://www.fuzzwork.co.uk/dump/latest"

# Sevey owned BPOs (deduped from AA export)
OWNED: set[str] = {
    "10000MN Afterburner I Blueprint",
    "100MN Afterburner I Blueprint",
    "100mm Steel Plates I Blueprint",
    "10MN Afterburner I Blueprint",
    "150mm Light AutoCannon I Blueprint",
    "150mm Railgun I Blueprint",
    "1MN Afterburner I Blueprint",
    "200mm AutoCannon I Blueprint",
    "200mm Railgun I Blueprint",
    "25000mm Crystalline Carbonide Restrained Plates Blueprint",
    "25000mm Steel Plates I Blueprint",
    "5MN Microwarpdrive I Blueprint",
    "800mm Steel Plates I Blueprint",
    "Acolyte I Blueprint",
    "Antimatter Charge S Blueprint",
    "Badger Blueprint",
    "Ballistic Control System I Blueprint",
    "Bantam Blueprint",
    "Berserker I Blueprint",
    "Blackbird Blueprint",
    "Breacher Blueprint",
    "Caldari Shuttle Blueprint",
    "Caracal Blueprint",
    "Carbon Fiber Reaction Formula",
    "Carbonized Lead S Blueprint",
    "Catalyst Blueprint",
    "Coherent Asteroid Mining Crystal Type B I Blueprint",
    "Coherent Asteroid Mining Crystal Type C I Blueprint",
    "Complex Asteroid Mining Crystal Type C I Blueprint",
    "Condor Blueprint",
    "Corax Blueprint",
    "Cormorant Blueprint",
    "Damage Control I Blueprint",
    "Data Analyzer I Blueprint",
    "Depleted Uranium S Blueprint",
    "Dragoon Blueprint",
    "Drone Damage Amplifier I Blueprint",
    "Dual 150mm Railgun I Blueprint",
    "Dual 180mm AutoCannon I Blueprint",
    "EMP S Blueprint",
    "Erratic Ore Mining Crystal Type A I Blueprint",
    "Erratic Ore Mining Crystal Type B I Blueprint",
    "Erratic Ore Mining Crystal Type C I Blueprint",
    "Expanded Cargohold I Blueprint",
    "Explosive Coating I Blueprint",
    "Ferox Blueprint",
    "Fusion S Blueprint",
    "Griffin Blueprint",
    "Hammerhead I Blueprint",
    "Heavy Initiated Compact Warp Scrambler Blueprint",
    "Heavy Missile Launcher I Blueprint",
    "Helium Fuel Block Blueprint",
    "Heron Blueprint",
    "Hobgoblin I Blueprint",
    "Hornet I Blueprint",
    "Hydrogen Fuel Block Blueprint",
    "Inferno Cruise Missile Blueprint",
    "Inferno Light Missile Blueprint",
    "Inferno Rocket Blueprint",
    "Infiltrator I Blueprint",
    "Kestrel Blueprint",
    "Large Processor Overclocking Unit I Blueprint",
    "Large Shield Extender I Blueprint",
    "Light Missile Launcher I Blueprint",
    "Medium Deep Core Mining Optimization I Blueprint",
    "Medium Shield Extender I Blueprint",
    "Merlin Blueprint",
    "Mining Laser Upgrade I Blueprint",
    "Mjolnir Cruise Missile Blueprint",
    "Mjolnir Heavy Assault Missile Blueprint",
    "Mjolnir Heavy Missile Blueprint",
    "Mjolnir Light Missile Blueprint",
    "Mjolnir Rocket Blueprint",
    "Moa Blueprint",
    "Multispectrum Coating I Blueprint",
    "Multispectrum Energized Membrane I Blueprint",
    "Naga Blueprint",
    "Nova Cruise Missile Blueprint",
    "Nova Heavy Missile Blueprint",
    "Nova Light Missile Blueprint",
    "Nova Rocket Blueprint",
    "Ogre I Blueprint",
    "Osprey Blueprint",
    "Oxy-Organic Solvents Reaction Formula",
    "Oxygen Fuel Block Blueprint",
    "Phased Plasma S Blueprint",
    "Power Diagnostic System I Blueprint",
    "Probe Blueprint",
    "Punisher Blueprint",
    "R.A.M.- Starship Tech Blueprint",
    "Reinforced Carbon Fiber Reaction Formula",
    "Relic Analyzer I Blueprint",
    "Salvage Drone I Blueprint",
    "Salvager I Blueprint",
    "Scourge Cruise Missile Blueprint",
    "Scourge Heavy Assault Missile Blueprint",
    "Scourge Heavy Missile Blueprint",
    "Scourge Light Missile Blueprint",
    "Scourge Rocket Blueprint",
    "Sensor Booster I Blueprint",
    "Simple Asteroid Mining Crystal Type B I Blueprint",
    "Simple Asteroid Mining Crystal Type C I Blueprint",
    "Small Auxiliary Nano Pump I Blueprint",
    "Small Cargohold Optimization I Blueprint",
    "Small Nanobot Accelerator I Blueprint",
    "Small Remote Repair Augmentor I Blueprint",
    "Small Shield Booster I Blueprint",
    "Small Tractor Beam I Blueprint",
    "Station Warehouse Container Blueprint",
    "Tayra Blueprint",
    "Thermosetting Polymer Reaction Formula",
    "Thorax Blueprint",
    "Titanium Sabot S Blueprint",
    "Tormentor Blueprint",
    "Uranium Charge S Blueprint",
    "Valkyrie I Blueprint",
    "Variegated Asteroid Mining Crystal Type A I Blueprint",
    "Variegated Asteroid Mining Crystal Type B I Blueprint",
    "Variegated Asteroid Mining Crystal Type C I Blueprint",
    "Venture Blueprint",
    "Vespa I Blueprint",
    "Vexor Blueprint",
    "Void Bomb Blueprint",
    "Warp Core Stabilizer I Blueprint",
    "Warrior I Blueprint",
    "Wasp I Blueprint",
}

SHIP_GROUPS = {
    "Shuttle",
    "Frigate",
    "Destroyer",
    "Cruiser",
    "Battlecruiser",
    "Battleship",
    "Industrial",
    "Freighter",
    "Capital Industrial Ship",
    "Mining Barge",
    "Exhumer",
    "Transport Ship",
    "Blockade Runner",
    "Combat Battlecruiser",
    "Command Ship",
    "Interdictor",
    "Logistics",
    "Covert Ops",
    "Electronic Attack Ship",
    "Heavy Assault Cruiser",
    "Heavy Interdiction Cruiser",
    "Interceptor",
    "Marauder",
    "Recon Ship",
    "Strategic Cruiser",
    "Prototype Exploration Ship",
}


def fetch_csv_bz2(name: str) -> str:
    url = f"{FUZZWORK}/{name}.csv.bz2"
    with urllib.request.urlopen(url, timeout=180) as resp:
        return bz2.decompress(resp.read()).decode("utf-8", errors="replace")


def fmt_isk(value: int) -> str:
    if value >= 1_000_000_000:
        return f"{value / 1_000_000_000:.2f} B ISK"
    if value >= 1_000_000:
        return f"{value / 1_000_000:.2f} M ISK"
    if value >= 1_000:
        return f"{value / 1_000:.0f} k ISK"
    return f"{value} ISK"


def display_name(type_name: str) -> str:
    """Match spreadsheet-style labels (no ' Blueprint' / ' Reaction Formula' suffix)."""
    if type_name.endswith(" Blueprint"):
        return type_name[: -len(" Blueprint")]
    if type_name.endswith(" Reaction Formula"):
        return type_name[: -len(" Reaction Formula")]
    return type_name


def collect_missing() -> tuple[list[tuple[str, int, str]], dict[int, str]]:
    groups = {
        int(row["groupID"]): row["groupName"]
        for row in csv.DictReader(io.StringIO(fetch_csv_bz2("invGroups")))
    }

    missing: list[tuple[str, int, str]] = []
    for row in csv.DictReader(io.StringIO(fetch_csv_bz2("invTypes"))):
        name = row["typeName"]
        if name in OWNED:
            continue
        try:
            base = int(float(row.get("basePrice") or 0))
            published = int(row.get("published") or 0)
            group_id = int(row.get("groupID") or 0)
        except (TypeError, ValueError):
            continue
        if not published or base <= 0:
            continue
        group_name = groups.get(group_id, "")
        is_bpo = name.endswith(" Blueprint") and (
            group_name.endswith(" Blueprint") or group_name == "Blueprint"
        )
        is_reaction = name.endswith(" Reaction Formula")
        if is_bpo or is_reaction:
            missing.append((name, base, group_name if is_bpo else "Reaction Formula"))

    missing.sort(key=lambda item: display_name(item[0]).casefold())
    return missing, groups


def main() -> None:
    missing, _groups = collect_missing()

    ships = [
        item
        for item in missing
        if item[2] in SHIP_GROUPS or item[2].endswith(" Blueprint") and any(
            hull in item[2]
            for hull in (
                "Frigate",
                "Cruiser",
                "Battleship",
                "Shuttle",
                "Destroyer",
                "Battlecruiser",
                "Industrial",
                "Freighter",
                "Barge",
                "Exhumer",
                "Transport",
                "Blockade",
                "Capital",
            )
        )
    ]
    reactions = [item for item in missing if item[2] == "Reaction Formula"]
    other = [item for item in missing if item not in ships and item not in reactions]

    print(f"Sevey owned (unique BPO/reactions): {len(OWNED)}")
    print(f"NPC-seedable missing (entire Tranquility catalog): {len(missing)}")
    print(f"  Ship hulls: {len(ships)}")
    print(f"  Reactions: {len(reactions)}")
    print(f"  Modules/ammo/drones/other: {len(other)}")
    print(f"Sum of all missing NPC seed prices: {fmt_isk(sum(p for _, p, _ in missing))}")
    print()

    def block(title: str, rows: list[tuple[str, int, str]]) -> None:
        print(f"### {title} ({len(rows)})")
        for name, price, _group in rows:
            print(f"| {name} | {fmt_isk(price)} |")
        print()

    block("Ship / hull BPOs missing", ships)
    block("Reaction formulas missing", reactions)
    block("Module / ammo / drone BPOs missing", other)


def write_tsv(path: str) -> int:
    """Write ``Name<TAB>NPC_seed_isk`` lines (spreadsheet-friendly)."""
    missing, _ = collect_missing()
    with open(path, "w", encoding="utf-8", newline="\n") as fh:
        for type_name, price, _group in missing:
            fh.write(f"{display_name(type_name)}\t{price}\n")
    return len(missing)


if __name__ == "__main__":
    import sys

    if len(sys.argv) > 1 and sys.argv[1] == "--tsv":
        out = sys.argv[2] if len(sys.argv) > 2 else "sevey_bpo_missing.tsv"
        count = write_tsv(out)
        print(f"Wrote {count} lines to {out}")
    else:
        main()
