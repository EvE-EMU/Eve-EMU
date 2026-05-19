# Standing Fleet Tracker (Alliance Auth)

Tracks **every fleet** linked characters join via ESI (no fleet link required), records ships and locations, and scores **standing fleet participation**.

## Points

| Event | Points |
|--------|--------|
| Hour in a **standing fleet** | +`SFT_POINTS_PER_STANDING_HOUR` (default 1) — not awarded for non-standing fleets |
| **Fleet pulse** (each poll roster snapshot) | +`SFT_PULSE_POINTS_PER_PULSE` (default 0.25) per linked character on the roster — any fleet |
| Killmail on **home defence** in sov | +`SFT_KILL_BONUS_POINTS` (default 5) |
| Hour **roaming sov** (system changes) while **not** in standing fleet | −`SFT_PENALTY_PER_SOV_ROAM_HOUR` (default 1) |

## Standing fleet detection

Configure via Django admin:

- **Standing fleet allowlist** — known `fleet_id` values
- Env **`SFT_STANDING_MOTD_SUBSTRINGS`** — plain-text match after stripping EVE HTML (e.g. `WOMP` matches `Welcome to WOMP Standing` in fleet MOTD). **Who commands the fleet does not matter.**
- **AFAT** fleet name on a FAT with matching `esi_fleet_id` (any FC)
- Fleet MOTD is often only readable via ESI when someone who can read fleet info (usually the boss) has a token on Auth; member tokens usually get 404 on `/fleets/{id}/`.

## URLs

- `/standing-fleet/` — overview
- `/standing-fleet/leaderboard/` — top pilots (user totals across characters)
- `/standing-fleet/lagging/` — low participation / penalties
- `/standing-fleet/user/<id>/` — combined score + characters
- `/standing-fleet/character/<id>/` — fleets, top ships, ledger

## Required ESI scopes (per character)

`esi-fleets.read_fleet.v1` `esi-location.read_location.v1` `esi-location.read_ship_type.v1` `esi-assets.read_assets.v1` `esi-killmails.read_killmails.v1`

Add these to your CCP application and re-link characters.

## Permissions

Grant **`standing_fleet_tracker | Can access standing fleet tracker`** to member groups.

### Charlink (recommended for scopes)

On **[Charlink](https://auth.eve-emu.com/charlink/)**, enable **Standing Fleet Tracker** when adding or updating a character. That requests:

- `esi-fleets.read_fleet.v1`
- `esi-location.read_location.v1`
- `esi-location.read_ship_type.v1`
- `esi-assets.read_assets.v1` (live ship fits in the View fit popup)
- `esi-killmails.read_killmails.v1`

Without `esi-fleets.read_fleet.v1`, the tracker cannot see whether you are in a fleet. Without `esi-assets.read_assets.v1`, View fit falls back to doctrine fits from the Fittings app only.

## Celery

- `sft_poll_all_characters` — every 2 minutes
- `sft_accrue_points` — hourly
- `sft_refresh_sov_cache` — every 6 hours
