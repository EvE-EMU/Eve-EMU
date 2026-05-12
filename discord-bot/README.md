# EvE-EMU Discord bot

Python bot for **INDEX / WOMP**–style EVE communities: mining timers, comms shortcuts, and optional hooks into the EvE-EMU API.

**EvE-EMU community Discord:** [discord.gg/DHMTKsMNbp](https://discord.gg/DHMTKsMNbp)

## Slash commands

- **`/miner timer`** — Register an ore anomaly respawn from **pop time** (system, anomaly name, UTC time). Duration is **inferred from the anomaly name** (e.g. Average → ~4h20m band, Large → ~10h band, Type A/B/C belt → A/B/C crystal band). Large / Enormous Mercoxit use fixed **8h / 12h** from the sheet. Uses autocomplete for systems and anomaly names where configured.
- **`/miner respawns`** — List timers whose respawn falls in a **±10 hour** window (EVE/UTC).
- **`/website`** — Reply with the configured alliance **EvE-EMU** site URL.
- **`/help`** — Short list of slash and text commands.
- **`/eve-link`** — Link the caller’s Discord account to EvE-EMU using a **one-time code** (API must expose the link endpoint).

> **`/structure`** (new timer + admin panel for vulnerability reminders) is implemented in code but **not** registered on the command tree at the moment; structure **feed** posts still work when the API is configured.

## Text commands (no slash permissions)

- **`!miner timer`** — Same as **`/miner timer`**. Optional prefix **`T1`/`T2`/`T3`** overrides the inferred band if the name alone is ambiguous.
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

## Moon timer pings (optional, no API)

- Polls the **[Moon Timers – FALSE GODS](https://docs.google.com/spreadsheets/d/1cDtuFQivlumB_HNZGVXWmZaHcPomFZT6r_zAe_G6VhY/edit?usp=sharing)** Google Sheet tab **`moon_timers`** as CSV (via Google’s `gviz` export).
- Set **`EVE_MOON_TIMERS_CHANNEL_ID`** to the Discord text channel for **`@here`** lead pings (default **30** minutes before the parsed “next” time; see **`EVE_MOON_TIMERS_LEAD_MINUTES`**).
- Rows need a **parseable date/time in `Next Timer`** (or another time-like column); currency and renter columns are ignored. Until those cells are filled, the bot will fetch the sheet but will not send pings.
- The sheet must allow **Anyone with the link can view** so the bot can fetch CSV without a Google login. Override the CSV URL with **`EVE_MOON_TIMERS_CSV_URL`** if you publish a copy elsewhere.

## API-backed features (when `EVEEMU_API_BASE_URL` + `MINING_BOT_DASHBOARD_TOKEN` are set)

- **Dashboard heartbeat** — POSTs bot status to your EvE-EMU integration URL if configured.
- **Industry watch DMs** — Polls the API and sends **direct messages** from queued industry notifications.
- **Structure timer board** — Polls the API and posts **embeds** to the configured Discord channel (sheet-driven timers + standings from corp ESI on the API side).
- **Market / stocker alerts** — Posts **embeds** (and optional role ping) from market-watch payloads (WOMPSTAR-style undercut/stock alerts when the API is set up).
- **Account notifications** — Delivers **DMs** from the API tick endpoint.
- **Buyback admin alerts** — Posts **channel updates** for buyback admin events when a channel id is set.
- **Corporation projects** — Posts **corp project** updates from ESI (via API token + channel routing on bot and server).

Configuration details and env var names live in the docstring at the top of **`bot/eve_mining_timer_bot.py`**.
