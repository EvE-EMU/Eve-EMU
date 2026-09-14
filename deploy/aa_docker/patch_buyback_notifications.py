"""Fix reverse buyback notification links in aa-buybackprogram 3.x."""

from __future__ import annotations

import pathlib

NOTIFICATION = pathlib.Path(
    "/usr/local/lib/python3.12/site-packages/buybackprogram/notification.py"
)

HELPER = '''

def _contract_path(message: dict) -> str:
    tracking = message["tracking"]
    if message.get("is_reverse"):
        return reverse(
            "buybackprogram:reverse_contract_details",
            args=[tracking.tracking_number],
        )
    return reverse(
        "buybackprogram:contract_details", args=[tracking.tracking_number]
    )


def _contract_url(message: dict) -> str:
    return f"{settings.SITE_URL}{_contract_path(message)}"
'''

OLD_DISCORD_DM = """        contract = message["contract"]
        tracking = message["tracking"]
        contract_path = reverse(
            "buybackprogram:contract_details", args=[tracking.tracking_number]
        )
        contract_url = f"{settings.SITE_URL}{contract_path}"
"""

NEW_DISCORD_DM = """        contract = message["contract"]
        tracking = message["tracking"]
        contract_url = _contract_url(message)
"""

OLD_USER_PATH = """    if message.get("is_reverse"):
        contract_path = reverse(
            "buybackprogram:reverse_contract_details", args=[tracking.tracking_number]
        )
    else:
        contract_path = reverse(
            "buybackprogram:contract_details", args=[tracking.tracking_number]
        )
    contract_url = f"{settings.SITE_URL}{contract_path}"

    msg = (
        "Date issued: "
        + str(contract.date_issued)
        + "\\n"
        + "Issued from: "
        + str(message["assigned_from"])
        + "\\n"
        + "Location: "
        + str(contract.location_name)
        + "\\n"
        + "Tracking #: "
        + str(tracking.tracking_number)
        + "\\n"
        + "Price #: "
        + str(intcomma(int(contract.price)))
        + " ISK"
        + "\\n"
    )
"""

NEW_USER_PATH = """    contract_url = _contract_url(message)

    msg = (
        "Date issued: "
        + str(contract.date_issued)
        + "\\n"
        + "Issued from: "
        + str(message["assigned_from"])
        + "\\n"
        + "Issued to: "
        + str(message.get("assigned_to", ""))
        + "\\n"
        + "Location: "
        + str(contract.location_name)
        + "\\n"
        + "Tracking #: "
        + str(tracking.tracking_number)
        + "\\n"
        + "Price #: "
        + str(intcomma(int(contract.price)))
        + " ISK"
        + "\\n"
        + "View Contract: "
        + contract_url
        + "\\n"
    )
"""

OLD_DISCORDPROXY_LINK = """            fields.append(
                Embed.Field(
                    name="Link",
                    value=str(message["[View Contract]({contract_url})"]),
                    inline=False,
                )
            )
"""

NEW_DISCORDPROXY_LINK = """            fields.append(
                Embed.Field(
                    name="Link",
                    value=f"[View Contract]({contract_url})",
                    inline=False,
                )
            )
"""

OLD_WEBHOOK = """    contract = message["contract"]
    tracking = message["tracking"]
    contract_path = reverse(
        "buybackprogram:contract_details", args=[tracking.tracking_number]
    )
    contract_url = f"{settings.SITE_URL}{contract_path}"
"""

NEW_WEBHOOK = """    contract = message["contract"]
    tracking = message["tracking"]
    contract_url = _contract_url(message)
"""


def main() -> None:
    # 2026-09-14: this used to `raise SystemExit` (nonzero exit -> failed
    # `docker build`) the moment any of its hardcoded anchor strings didn't
    # match the installed `buybackprogram` package's actual source verbatim
    # — which is exactly what happened here: a routine dependency bump
    # changed `notification.py`'s text enough to break the match, and took
    # the *entire* aa-web/aa-worker/aa-beat build down with it, for a purely
    # cosmetic fix (a Discord embed's contract link rendering as a literal
    # dict-key string instead of a markdown link). A cosmetic notification-
    # formatting patch should never be able to block deploying the whole
    # platform. Every step below now warns and moves on instead of aborting
    # — worst case, that one Discord link looks slightly off until this
    # patch is updated for the new upstream source, which is a far smaller
    # problem than nothing being deployable at all.
    text = NOTIFICATION.read_text(encoding="utf-8")
    if "_contract_url(message" in text:
        print("patch_buyback_notifications: already applied")
        return

    if "def _contract_url(message" not in text:
        marker = "logger = get_extension_logger(__name__)\n\n\n"
        if marker not in text:
            print(
                "patch_buyback_notifications: insertion point not found — "
                "upstream buybackprogram's notification.py has changed shape; "
                "skipping this patch rather than failing the build."
            )
            return
        text = text.replace(marker, marker + HELPER.lstrip() + "\n\n", 1)

    applied = 0
    for old, new in (
        (OLD_DISCORD_DM, NEW_DISCORD_DM),
        (OLD_USER_PATH, NEW_USER_PATH),
        (OLD_DISCORDPROXY_LINK, NEW_DISCORDPROXY_LINK),
        (OLD_WEBHOOK, NEW_WEBHOOK),
    ):
        if old not in text:
            print(f"patch_buyback_notifications: expected block not found, skipping:\n{old[:80]}...")
            continue
        text = text.replace(old, new, 1)
        applied += 1

    if applied:
        NOTIFICATION.write_text(text, encoding="utf-8")
    print(f"patch_buyback_notifications: applied {applied}/4 block(s)")


if __name__ == "__main__":
    main()
