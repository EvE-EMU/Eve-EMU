from eve_sde.models import (
    Constellation,
    ItemGroup,
    ItemType,
    ItemTypeMaterials,
    Region,
    SolarSystem,
)

_GROUPS = {
    18: "Ore Materials",
    450: "Standard Ore",
    465: "Ice",
    468: "Mercoxit",
    711: "Gas",
    1884: "R4 Moon Ore",
    1920: "R8 Moon Ore",
    1921: "R16 Moon Ore",
    1922: "R32 Moon Ore",
    1923: "R64 Moon Ore",
}

_ITEM_TYPES = {
    1230: {"name": "Veldspar", "group_id": 450, "portion_size": 100, "base_price": 5},
    11396: {"name": "Mercoxit", "group_id": 468, "portion_size": 100, "base_price": 20},
    16267: {
        "name": "Blue Ice",
        "group_id": 465,
        "portion_size": 1000,
        "base_price": 15,
    },
    16635: {"name": "Titanium", "group_id": 18, "portion_size": 1, "base_price": 2},
    28695: {
        "name": "Amber Cytoserocin",
        "group_id": 711,
        "portion_size": 1,
        "base_price": 12,
    },
    45492: {"name": "Bitumens", "group_id": 1884, "portion_size": 100, "base_price": 8},
    45496: {
        "name": "Cobaltite",
        "group_id": 1920,
        "portion_size": 100,
        "base_price": 8,
    },
    45501: {
        "name": "Carnotite",
        "group_id": 1921,
        "portion_size": 100,
        "base_price": 8,
    },
    45503: {"name": "Xenotime", "group_id": 1922, "portion_size": 100, "base_price": 8},
    45511: {
        "name": "Monazite",
        "group_id": 1923,
        "portion_size": 100,
        "base_price": 10,
    },
    62586: {
        "name": "Compressed Kernite",
        "group_id": 450,
        "portion_size": 1,
        "base_price": 10,
    },
}

_SOLAR_SYSTEMS = {
    30000142: {"name": "Jita", "security_status": 0.9, "visual_effect": None},
    30002537: {"name": "Amamake", "security_status": 0.4, "visual_effect": None},
    31000005: {"name": "J123456", "security_status": -0.1, "visual_effect": None},
    30010001: {
        "name": "Pochven Prime",
        "security_status": -0.2,
        "visual_effect": "TRIGLAVIAN_HOME",
    },
}


def load_eve_sde():
    region, _ = Region.objects.update_or_create(
        id=10000001, defaults={"name": "Test Region"}
    )
    constellation, _ = Constellation.objects.update_or_create(
        id=20000001,
        defaults={"name": "Test Constellation", "region": region},
    )

    for group_id, name in _GROUPS.items():
        ItemGroup.objects.update_or_create(
            id=group_id,
            defaults={"name": name, "published": True},
        )

    for type_id, data in _ITEM_TYPES.items():
        ItemType.objects.update_or_create(
            id=type_id,
            defaults={
                "name": data["name"],
                "group_id": data["group_id"],
                "portion_size": data["portion_size"],
                "base_price": data["base_price"],
                "published": True,
            },
        )

    for system_id, data in _SOLAR_SYSTEMS.items():
        SolarSystem.objects.update_or_create(
            id=system_id,
            defaults={
                "name": data["name"],
                "security_status": data["security_status"],
                "visual_effect": data["visual_effect"],
                "constellation": constellation,
            },
        )


def add_material(item_type_id: int, material_type_id: int, quantity: int):
    ItemTypeMaterials.objects.update_or_create(
        item_type_id=item_type_id,
        material_item_type_id=material_type_id,
        defaults={"quantity": quantity},
    )
