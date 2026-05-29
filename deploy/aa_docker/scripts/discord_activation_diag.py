"""One-off Discord activation diagnostics (run via manage.py shell)."""
from __future__ import annotations

import requests
from django.contrib.auth.models import User

from allianceauth.services.modules.discord.app_settings import DISCORD_BOT_TOKEN, DISCORD_GUILD_ID
from allianceauth.services.modules.discord.core import calculate_roles_for_user, create_bot_client

GUILD = int(DISCORD_GUILD_ID)
TARGET_UID = 836098226809602058
USERNAME = "sevey"
headers = {"Authorization": f"Bot {DISCORD_BOT_TOKEN}"}


def main() -> None:
    me = requests.get("https://discord.com/api/users/@me", headers=headers, timeout=15).json()
    bot_id = me["id"]
    print(f"BOT_USER={me.get('username')} id={bot_id}")

    bot_m = requests.get(
        f"https://discord.com/api/guilds/{GUILD}/members/{bot_id}",
        headers=headers,
        timeout=15,
    )
    print(f"BOT_IN_GUILD={bot_m.status_code}")
    bot_role_ids = bot_m.json().get("roles", []) if bot_m.ok else []

    tm = requests.get(
        f"https://discord.com/api/guilds/{GUILD}/members/{TARGET_UID}",
        headers=headers,
        timeout=15,
    )
    print(f"TARGET_MEMBER={tm.status_code}")
    target_roles = tm.json().get("roles", []) if tm.ok else []

    roles = requests.get(
        f"https://discord.com/api/guilds/{GUILD}/roles", headers=headers, timeout=15
    ).json()
    by_id = {r["id"]: r for r in roles}

    def top_pos(role_ids: list[str]) -> int:
        return max((by_id[r]["position"] for r in role_ids if r in by_id), default=-1)

    bot_pos = top_pos(bot_role_ids)
    target_pos = top_pos(target_roles)
    print(f"BOT_HIGHEST_POSITION={bot_pos}")
    print(f"TARGET_HIGHEST_POSITION={target_pos}")
    print(f"BOT_CAN_MANAGE_TARGET={bot_pos > target_pos}")

    user = User.objects.get(username=USERNAME)
    client = create_bot_client(is_rate_limited=False)
    roles_calc, changed = calculate_roles_for_user(
        user=user, client=client, discord_uid=TARGET_UID
    )
    print(f"CHANGED_FLAG={changed}")
    assign = list(roles_calc.ids()) if roles_calc else []
    print(f"ROLES_TO_ASSIGN={assign}")
    for rid in assign:
        r = by_id.get(str(rid))
        if r:
            above_bot = r["position"] >= bot_pos
            print(
                f"  role={r['name']!r} pos={r['position']} "
                f"managed={r.get('managed')} ABOVE_OR_EQ_BOT={above_bot}"
            )

    print("TARGET_MEMBER_ROLES (highest first):")
    for rid in sorted(target_roles, key=lambda x: by_id.get(x, {}).get("position", -1), reverse=True):
        r = by_id.get(rid)
        if r:
            blocks = " *** BLOCKS BOT ***" if r["position"] >= bot_pos else ""
            print(f"  {r['name']!r} pos={r['position']}{blocks}")

    print("BOT_MEMBER_ROLES (highest first):")
    for rid in sorted(bot_role_ids, key=lambda x: by_id.get(x, {}).get("position", -1), reverse=True):
        r = by_id.get(rid)
        if r:
            print(f"  {r['name']!r} pos={r['position']}")


if __name__ == "__main__":
    main()
