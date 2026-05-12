# EvE-EMU Discord bot

Python bot for **INDEX / WOMP**–style EVE communities: mining timers, comms shortcuts, and optional hooks into the EvE-EMU API.

## Slash commands

- **`/miner timer`** — Register a **T1 / T2 / T3** ore anomaly respawn timer (system name, anomaly type, EVE/UTC time). Uses autocomplete for systems and anomaly names where configured.
- **`/miner respawns`** — List timers whose respawn falls in a **±10 hour** window (EVE/UTC).
- **`/website`** — Reply with the configured alliance **EvE-EMU** site URL.
- **`/help`** — Short list of slash and text commands.
- **`/eve-link`** — Link the caller’s Discord account to EvE-EMU using a **one-time code** (API must expose the link endpoint).

> **`/structure`** (new timer + admin panel for vulnerability reminders) is implemented in code but **not** registered on the command tree at the moment; structure **feed** posts still work when the API is configured.

## Text commands (no slash permissions)

- **`!miner timer`** — Same behavior as **`/miner timer`** after the tier token (`T1` / `T2` / `T3`).
- **`!miner respawns`** — Same as **`/miner respawns`** (also accepts **`!miner resawns`** as a typo alias).
- **`!help`** — Lists the main text commands.
- **`!srp`**, **`!auth`**, **`!mumble`**, **`!intel`**, **`!buyback`** — Static alliance links and guides (mumble can attach a push-to-talk GIF when the file is present).
- **`!eve-link`** — Same linking flow as **`/eve-link`**, in-channel; put the six-digit code after the command.
- **`!popejoy`** — Channel joke line (hard-coded).
- **`!testping`** — Preview a mining ping layout; pass the belt / anomaly label after the command.

## Mining pings and timers

- Persists timers to disk; on respawn (or **N minutes before**, default 30) posts **`@here`** pings in the channel where the timer was created.
- Optional **belt-type images** and extra lines for specific anomalies (e.g. Griemeer) when image paths are configured.
- **Buyback tip** line on certain ping types when enabled in code.

## Member welcome (optional)

- On **first join** in a configured guild, can post a **welcome** message in a designated channel (no spam on rejoin).

## API-backed features (when `EVEEMU_API_BASE_URL` + `MINING_BOT_DASHBOARD_TOKEN` are set)

- **Dashboard heartbeat** — POSTs bot status to your EvE-EMU integration URL if configured.
- **Industry watch DMs** — Polls the API and sends **direct messages** from queued industry notifications.
- **Structure timer board** — Polls the API and posts **embeds** to the configured Discord channel (sheet-driven timers + standings from corp ESI on the API side).
- **Market / stocker alerts** — Posts **embeds** (and optional role ping) from market-watch payloads (WOMPSTAR-style undercut/stock alerts when the API is set up).
- **Account notifications** — Delivers **DMs** from the API tick endpoint.
- **Buyback admin alerts** — Posts **channel updates** for buyback admin events when a channel id is set.
- **Corporation projects** — Posts **corp project** updates from ESI (via API token + channel routing on bot and server).

Configuration details and env var names live in the docstring at the top of **`bot/eve_mining_timer_bot.py`**.
