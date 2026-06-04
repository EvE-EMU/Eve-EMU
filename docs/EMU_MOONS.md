# EMU Moons (Alliance Auth 5)

EMU Moons is a bolt-on Django app in `deploy/aa_docker/emu_moons/` that automates moon mining tax invoicing while **reusing** existing data from:

- **aa-moonmining** — extractions, structures, moon surveys
- **aa-miningtaxes** — observer mining logs (`AdminMiningObsLog`) and ore prices (`OrePrices`)

No migration of moonmining or miningtaxes data is required. EMU Moons adds its own tables only.

## Install (Docker stack)

1. Rebuild AA images (Dockerfile copies `emu_moons`):
   ```powershell
   docker compose build aa-web aa-worker aa-beat
   docker compose up -d aa-web aa-worker aa-beat
   ```
2. Migrate and seed defaults:
   ```powershell
   docker compose exec aa-web python manage.py migrate emu_moons
   docker compose exec aa-web python manage.py emu_moons_seed
   ```
3. **Access** (automatic; Django group perms are optional extras):
   - **Naughty list** — public (guests and members), `/emu-moons/naughty/`
   - **My statement** — any logged-in member
   - **Corporation** — any logged-in member (their main character’s corp)
   - **Alliance** + **All accounts** — **sevey**, **Rexan Darkstar**, or any linked character with Director (or `Config_Starbase_Equipment`) ESI roles
   - **Admin** — `emu_moons.emu_moons_admin` only

4. Rebuild invoices after fixing attribution (e.g. per-character mining in `0TKF-6`):
   ```powershell
   docker compose exec aa-web python manage.py migrate emu_moons
   docker compose exec aa-web python manage.py emu_moons_rebuild_invoices --system 0TKF-6
   ```

6. Clear test invoices before go-live (optional):
   ```powershell
   docker compose exec aa-web python manage.py emu_moons_clear_pre_cutoff
   ```
   Uses `tax_effective_date` on EMU Moons settings (default **2026-06-01**). Nothing before that date appears on statements or the naughty list.

## Configuration

**Django admin** (`/admin/emu_moons/`):

| Model | Purpose |
|-------|---------|
| EMU Moons settings | Tax corp, wallet division, ESI token, mail sender, grace/penalty days |
| Structure tax profile | Public / Nationalized / Private per refinery |
| Moon type tax rate | R4–R64 % by structure class (seeded by `emu_moons_seed`) |
| Discord webhook config | Notification types, mentions |
| Emu extraction / invoice | Audit and manual fixes |

**Environment** (optional):

| Variable | Default | Meaning |
|----------|---------|---------|
| `AA_EMU_MOONS_CELERY` | `1` | Enable beat tasks |
| `AA_EMU_MOONS_INVOICE_WEEKDAY` | `3` | Weekly run (0=Mon, 3=Thu) |
| `AA_EMU_MOONS_INVOICE_HOUR_UTC` | `12` | Weekly run hour UTC |
| `AA_FALSE_GODS_CORP_TOKEN_ID` | — | Corp wallet ESI token PK fallback |
| `AA_EMU_MOONS_EXCLUDED_MOONS` | built-in list | Semicolon-separated moon labels excluded from tax (see below) |
| `MININGTAXES_TAX_ONLY_CORP_MOONS` | `0` when emu_moons installed | Must be off so personal ledgers store moon ores for invoicing |

### Tax-exempt moons (not tracked / not invoiced)

By default these are **excluded** from member-mining import, extraction discovery, and invoicing:

- RF-CN3 V - Moon 6 and Moon 8
- 9-HMO4 IV - Moon 6
- DS- structures whose name includes **P7M5** (e.g. DS-LO3 … P7M5; YW-SYT P7M5 is still taxed)

Override or extend via `AA_EMU_MOONS_EXCLUDED_MOONS` (semicolon-separated labels). Apply to existing rows:

```powershell
docker compose exec aa-web python manage.py emu_moons_apply_moon_exclusions
```

## How it works

1. **Discovery** — Celery reads completed `moonmining.models.Extraction` rows into `EmuExtraction`.
2. **Ledger match** — Within `ledger_match_hours` (default 48) after pop: corp **`AdminMiningObsLog`** when available (per miner, per ore); otherwise **`CharacterMiningLedgerEntry`** in that system (personal mining — typical on emu).
3. **Invoicing** — **One invoice per character per pop** (`MT-YYWW-XXXX`), ore lines match what that character mined (not the whole pop total).
4. **Delivery** — ESI mail from configured sender; Discord embed on extraction complete.
5. **Payment** — Corp wallet journal matches per-invoice `MT-YYWW-XXXX` or consolidated **`MT-MAIN{character_id}EMU`** (main character ID on the account).
6. **Penalties** — After 30 days grace, 100% of original balance per week overdue; corp liability at 60 days.

## UI

| URL | Who |
|-----|-----|
| `/emu-moons/naughty/` | Everyone (guest) |
| `/emu-moons/account/` | Logged-in member (own statement) |
| `/emu-moons/corp/` | Logged-in member (own corp) |
| `/emu-moons/invoices/` | sevey, Rexan, directors |
| `/emu-moons/alliance/` | sevey, Rexan, directors |
| `/emu-moons/admin/settings/` | `emu_moons_admin` |

**Scheduling assistant** — On `/moonmining/extractions`, users with `emu_moons_view_alliance` or `emu_moons_admin` see a **Next Extractions** table with suggested pop times per refinery.

**Moon calendar** — `/moonmining/calendar` shows scheduled chunk arrivals and suggested next pops, color-coded by structure class (public / nationalized / private). Members with `moonmining.extractions_access` see public and nationalized moons. **Private moon owners** assigned in `/emu-moons/admin/settings/` also see their private moons (calendar nav appears for them even without extractions access). Alliance admin sees all private moons.

Survey export on `/moonmining/reports` remains Phase 2.

### Member Mining (`/moonmining/reports`)

The **Member Mining** tab reads `moonmining` `MiningLedgerRecord` rows (corp structure observers via ESI). If the table is empty, import once:

```powershell
docker compose exec aa-web python manage.py moonmining_sync_reports
```

This command:

1. Creates **Structure tax profile** rows for every refinery — **public** by default, **nationalized** if the structure name contains that word, **private** only when the name contains `PRIVATE` (or you assign a private owner in `/emu-moons/admin/settings/`).
2. Refreshes **miningtaxes** corp observer logs (`AdminMiningObsLog`) for invoicing.
3. Pulls moonmining ledgers for **all non-private** refineries only.

**Moon tax invoices** only include true **moon ores** (EVE groups R4–R64 — same set as [cerlestes moon table](https://ore.cerlestes.de/moon)). Belt ores mined at a moon (Kylixium, Gneiss, Jaspet, etc.) are excluded. Ledger data must come from **corp mining observers** (`AdminMiningObsLog`), not personal character ledgers.

Celery (when `emu_moons` is installed) runs `emu_moons.tasks.sync_moonmining_reports` hourly instead of the stock `moonmining.tasks.run_report_updates`, so private moons stay out of the automatic import.

Miners only appear when they have an Alliance Auth account linked to the mining character (`CharacterOwnership`).

If corp mining observer ESI returns no data (common on emu), import from existing **miningtaxes character ledgers** in moon systems (e.g. May 2026 has thousands of rows):

```powershell
docker compose exec aa-web python manage.py moonmining_sync_reports --from-character-ledger
# Or one month: --year 2026 --month 5
```

The report API also falls back to character ledgers directly when `MiningLedgerRecord` is empty.

## Celery tasks

| Task | Schedule |
|------|----------|
| `emu_moons.tasks.discover_extractions` | Every 15 min |
| `emu_moons.tasks.process_pending_invoices` | Every 2 h |
| `emu_moons.tasks.weekly_invoice_run` | Thursday 12:00 UTC (configurable) |
| `emu_moons.tasks.poll_wallet_payments` | Every 30 min |
| `emu_moons.tasks.refresh_penalties` | Daily 06:00 UTC |
| `emu_moons.tasks.refresh_ore_prices` | Every 6 h |
| `emu_moons.tasks.send_reminders` | Daily 10:00 UTC |

## Relationship to other apps

- **miningtaxes** — Keep installed for observer logs and price preload; stock UI remains available.
- **moon_tsar** — Disabled in slim bundle; EMU Moons supersedes that experiment.
- **moon_rentals** — Removed from the slim bundle (was `/miningtaxes/schedule/`).

## Spec gaps (Phase 2)

- Moon survey CSV/XLSX/JSON export button on reports
- Full Janice API integration (currently uses miningtaxes `OrePrices` snapshots)
- CEO / Discord escalation for corp liability and overdue CEO notify
- XLSX export on naughty list and alliance dashboard
