from app_utils.django import clean_setting

MININGTAXES_CORP_WALLET_DIVISION = clean_setting("MININGTAXES_CORP_WALLET_DIVISION", 1)

MININGTAXES_TAX_ONLY_CORP_MOONS = clean_setting("MININGTAXES_TAX_ONLY_CORP_MOONS", True)
"""Only tax corporate moons using moon observers as opposed to all moons appearing
in the personal mining ledgers.
"""

MININGTAXES_UPDATE_LEDGER_STALE = clean_setting("MININGTAXES_UPDATE_LEDGER_STALE", 240)
"""Minutes after which a character's mining ledger is considered stale
"""

MININGTAXES_UPDATE_STALE_OFFSET = clean_setting("MINGINGTAXES_UPDATE_STALE_OFFSET", 5)
"""Actual value for considering staleness of a ring will be the above value
minus this offset. Required to avoid time synchronization issues.
"""

MININGTAXES_TASKS_OBJECT_CACHE_TIMEOUT = clean_setting(
    "MEMBERAUDIT_TASKS_OBJECT_CACHE_TIMEOUT", 600
)

MININGTAXES_TASKS_TIME_LIMIT = clean_setting("MININGTAXES_TASKS_TIME_LIMIT", 7200)
"""Global timeout for tasks in seconds to reduce task accumulation during outages."""

MININGTAXES_REFINED_RATE = clean_setting("MININGTAXES_REFINED_RATE", 0.9063)
"""Refining rate for ores."""

MININGTAXES_ALLOW_ANALYTICS = clean_setting("MININGTAXES_ALLOW_ANALYTICS", True)

MININGTAXES_UNKNOWN_TAX_RATE = clean_setting("MININGTAXES_UNKNOWN_TAX_RATE", 0.10)

MININGTAXES_ALWAYS_TAX_REFINED = clean_setting("MININGTAXES_ALWAYS_TAX_REFINED", False)

MININGTAXES_PRICE_SOURCE_ID = clean_setting("MININGTAXES_PRICE_SOURCE_ID", 60003760)

MININGTAXES_PRICE_SOURCE_NAME = clean_setting("MININGTAXES_PRICE_SOURCE_NAME", "Jita")

MININGTAXES_PRICE_METHOD = clean_setting("MININGTAXES_PRICE_METHOD", "Fuzzwork")

MININGTAXES_PRICE_JANICE_API_KEY = clean_setting("MININGTAXES_PRICE_JANICE_API_KEY", "")

MININGTAXES_PRICE_JANICE_TIMING = clean_setting(
    "MININGTAXES_PRICE_JANICE_TIMING", "top5AveragePrices"
)
MININGTAXES_PRICE_JANICE_BUY = clean_setting(
    "MININGTAXES_PRICE_JANICE_BUY", "buyPrice5DayMedian"
)
MININGTAXES_PRICE_JANICE_SELL = clean_setting(
    "MININGTAXES_PRICE_JANICE_SELL", "sellPrice5DayMedian"
)


MININGTAXES_BLACKLIST = clean_setting("MININGTAXES_BLACKLIST", [])

MININGTAXES_TAX_HISEC = clean_setting("MININGTAXES_TAX_HISEC", True)
MININGTAXES_TAX_LOSEC = clean_setting("MININGTAXES_TAX_LOSEC", True)
MININGTAXES_TAX_NULLSEC = clean_setting("MININGTAXES_TAX_NULLSEC", True)
MININGTAXES_TAX_JSPACE = clean_setting("MININGTAXES_TAX_JSPACE", True)
MININGTAXES_TAX_POCHVEN = clean_setting("MININGTAXES_TAX_POCHVEN", True)

MININGTAXES_WHITELIST = clean_setting("MININGTAXES_WHITELIST", [])

MININGTAXES_LEADERBOARD_TAXABLE_ONLY = clean_setting(
    "MININGTAXES_LEADERBOARD_TAXABLE_ONLY", False
)

MININGTAXES_PING_FIRST_MSG = clean_setting(
    "MININGTAXES_PING_FIRST_MSG",
    "Please pay {:,.2f} ISK or you will be charged interest!",
)
MININGTAXES_PING_SECOND_MSG = clean_setting(
    "MININGTAXES_PING_SECOND_MSG",
    "Please pay {:,.2f} ISK or you will be charged interest!",
)
MININGTAXES_PING_THRESHOLD = clean_setting("MININGTAXES_PING_THRESHOLD", 0.01)

MININGTAXES_PING_CURRENT_THRESHOLD = clean_setting(
    "MININGTAXES_PING_CURRENT_THRESHOLD", 1000000000
)

MININGTAXES_PING_CURRENT_MSG = clean_setting(
    "MININGTAXES_PING_CURRENT_MSG",
    "Please pay your taxes. Current tax balance: {:,.2f} ISK",
)

MININGTAXES_PING_INTEREST_APPLIED = clean_setting(
    "MININGTAXES_PING_INTEREST_APPLIED",
    "An interest of {:,.2f} ISK has been charged for late taxes.",
)
