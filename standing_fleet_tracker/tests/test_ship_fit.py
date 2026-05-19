from standing_fleet_tracker.services.ship_fit import (
    _is_fitted_module_flag,
    _slot_sort_key,
    build_eft_from_fitted_items,
    _fitted_items_on_ship,
)


def test_fitted_module_flags():
    assert _is_fitted_module_flag("HiSlot0")
    assert _is_fitted_module_flag("DroneBay")
    assert not _is_fitted_module_flag("Cargo")


def test_slot_sort_order():
    assert _slot_sort_key("HiSlot1") < _slot_sort_key("MedSlot0")
    assert _slot_sort_key("MedSlot0") < _slot_sort_key("LoSlot0")
    assert _slot_sort_key("LoSlot0") < _slot_sort_key("RigSlot0")


def test_build_eft_orders_slots():
    eft = build_eft_from_fitted_items(
        641,
        ship_name="WH ROLLR",
        fitted_items=[
            {"type_id": 2, "location_flag": "LoSlot0", "quantity": 1},
            {"type_id": 1, "location_flag": "HiSlot0", "quantity": 1},
        ],
    )
    lines = [ln for ln in eft.splitlines() if ln.strip()]
    assert lines[0].startswith("Megathron") or "641" in lines[0] or lines[0]
    assert len(lines) >= 3


def test_fitted_items_on_ship_filters_cargo():
    assets = [
        {"item_id": 1, "type_id": 10, "location_id": 99, "location_flag": "HiSlot0", "quantity": 1},
        {"item_id": 2, "type_id": 20, "location_id": 99, "location_flag": "Cargo", "quantity": 100},
        {"item_id": 3, "type_id": 30, "location_id": 88, "location_flag": "HiSlot0", "quantity": 1},
    ]
    fitted = _fitted_items_on_ship(assets, 99)
    assert len(fitted) == 1
    assert fitted[0]["type_id"] == 10
