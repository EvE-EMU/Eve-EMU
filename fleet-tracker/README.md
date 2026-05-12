# Fleet tracker (EVE-EMU)

Planned service for **fleet.eve-emu.com** (container behind your edge proxy). Tracks linked characters’ fleet participation, movement, ships, and killmails using **EVE SSO + ESI**, with polling biased toward **active** users to limit token refresh and ESI load.

## Goals

| Requirement | ESI / approach |
|-------------|----------------|
| Which fleet each tracked character is in | [GetCharactersCharacterIdFleet](https://developers.eveonline.com/api-explorer#/operations/GetCharactersCharacterIdFleet) — `GET /characters/{character_id}/fleet/` (404 if not in a fleet). Scope: **`esi-fleets.read_fleet.v1`**. |
| “Joined WOMP Standing” or not | ESI does **not** expose a stable “fleet name” for arbitrary fleets. Practical options: (1) match **fleet MOTD** / patterns from **`GET /fleets/{fleet_id}/`** (requires **`esi-fleets.read_fleet_information.v1`** on a character that is **fleet boss** or otherwise allowed to read fleet info), (2) allowlist **fleet IDs** or **commander character IDs** configured in env, (3) match **motd** text against `WOMP` / `Standing`. |
| Who is in the fleet | **`GET /fleets/{fleet_id}/members/`** — same **fleet-information** scope; typically only reliable if you have an **FC / boss–linked** token. Otherwise you only see **self** from each participant’s token. |
| Time in fleet | `join_time` from **`/fleets/{fleet_id}/members/`** (FC view) or **first seen in fleet** timestamp from your own polls on each character. |
| Ship while in fleet | **`GET /characters/{character_id}/ship/`** — scope **`esi-ships.read_ships.v1`**. |
| “Fitting” while in fleet | ESI exposes **ship type** and **ship name** for the active ship, **not** live high/mid/low/rig module slots. Full fits require out-of-band data (client logs, third-party, or post-killmail reconstruction). Document as **ship_type + named ship** only unless you add non-ESI ingestion. |
| Systems visited in fleet | Poll **`GET /characters/{character_id}/location/`** (`**esi-location.read_location.v1**`) on an interval while `in_fleet`; append distinct `solar_system_id` + timestamp to a session trail. |
| Kills / losses | **`GET /characters/{character_id}/killmails/recent/`** + resolve killmail hashes (**`esi-killmails.read_killmails.v1`**). Optionally **zKill RedisQ** or **killmail stream** later for alliance-wide feed without per-character polling. |

## “Online users only”

ESI does not expose “logged into Tranquility right now” for arbitrary characters in a cheap way. Recommended definitions:

1. **App-active** (default): only poll users who have used the site recently (e.g. session / heartbeat in last N minutes) or who toggled **“track me now”**.
2. **ESI-online hint**: optional slower poll using **`GET /characters/{character_id}/online/`** (`**esi-location.read_online.v1**`) — useful signal, not real-time.

Combine with **staggered polling** and ESI cache timers (character fleet is short-cache; respect `Expires` / error limits).

## Auth model

- **Participant OAuth**: each user links a character; store refresh token encrypted at rest; scopes at minimum:  
  `esi-fleets.read_fleet.v1` `esi-location.read_location.v1` `esi-ships.read_ships.v1` `esi-killmails.read_killmails.v1`  
  Optional: `esi-location.read_online.v1`
- **Fleet commander OAuth** (optional but powerful): one (or few) FC accounts with **`esi-fleets.read_fleet_information.v1`** to pull full member list, join times, and fleet MOTD for classification.

## Data store

- **Postgres** (recommended): users, linked characters, encrypted tokens, `fleet_session` (open/close, fleet_id, womp_match flag), `fleet_session_member` (if FC feed), `location_sample`, `killmail_ref`, materialized views for UI.
- **Redis**: job queues, rate-limit coordination, session cache.

## API / UI

- **Backend**: FastAPI (this scaffold) + async HTTP to `https://esi.evetech.net/latest/...`.
- **Frontend**: separate SPA or server-rendered pages; host at **fleet.eve-emu.com** behind TLS terminator.

## Deployment

- Build with **`Dockerfile`** in this directory.
- Wire **fleet.eve-emu.com** in your reverse proxy to the container; set **`FLEET_TRACKER_PUBLIC_BASE_URL`** and SSO callback URLs accordingly.

See **`app/config.py`** for environment variables to implement next.

## References

- [GetCharactersCharacterIdFleet](https://developers.eveonline.com/api-explorer#/operations/GetCharactersCharacterIdFleet) (EVE Developers API Explorer)
- [EVE SSO documentation](https://docs.esi.evetech.net/docs/sso/)
- [ESI rate limits and best practices](https://docs.esi.evetech.net/docs/resource_guidelines/)
