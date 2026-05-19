"""EVE static identifiers used by corp_orders."""

import os

# Nitrogen Isotopes (Strontium Clathrates group) — Rhea jump fuel reference.
NITROGEN_ISOTOPES_TYPE_ID = 17888

# Default final-destination system on new orders (autocomplete seed / top of list).
DEFAULT_FINAL_DESTINATION_SYSTEM = os.environ.get(
    "CORP_ORDERS_DEFAULT_DESTINATION_SYSTEM", "3-F"
).strip() or "3-F"

SPEED_EXPIRATION_HOURS = {
    "god": 6,
    "alter": 66,
    "regular": 168,
}

SPEED_DESCRIPTION_LABEL = {
    "god": "God Speed (6 Hours or Less)",
    "alter": "Alter Speed (66 Hours or Less)",
    "regular": "Regular Speed (7 Days)",
}
