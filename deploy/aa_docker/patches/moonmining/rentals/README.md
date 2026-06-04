# Moon Rentals (`moonrentals`) — not deployed on eve-emu

> **Note:** This submodule is **not** installed in the eve-emu Docker bundle (removed from `INSTALLED_APPS`, image COPY, URLs, and Celery beat). Kept in-repo for reference or manual re-enable.

Renter management extension for **aa-moonmining**: track active moon leases, list available surveyed moons, verify rent via corp wallet journal, and post fuel/payment alerts to Discord.

Django app label: **`moonrentals`** (package path: `moonmining.rentals`).

## Features

| Area | Description |
|------|-------------|
| **Active leases** | Renter corp, main POC, monthly ISK, payment status, fuel %, edit/evict |
| **Available moons** | Surveyed moons with **no refinery** and **no active lease** — storefront for new rentals |
| **Admin settings (in-app)** | Wallet division, payment keyword, due day, grace period, Discord webhooks, auto-approve, fuel reference hours — **no `.env` required** for webhooks |
| **Wallet automation** | Celery polls corp wallet journal; matches `payment_keyword` + lease location in description |
| **Fuel sync** | Derives fuel % from **aa-structures** `hours_fuel_expires` (optional CorpTools fallback) |
| **Discord** | Low-fuel and payment-received rich embeds |
| **POC autocomplete** | Search Alliance Auth users by main character when editing a lease |
| **Applications** | Renters with `apply_rent` submit requests; optional **auto-approve** or manual approve/reject |

## UI

| Page | URL |
|------|-----|
| Renter Management | `/moonmining/renters/` |
| Configure lease | `/moonmining/renters/moon/<moon_id>/` |

Navigation: **Moon Mining → Renter Management** (requires `moonrentals.view_leases`).

### Tabs

1. **Active Leases** — open rentals; admins see fuel % and Edit/Evict; pending applications table when manual review is used.
2. **Available Moons** — moons with survey data but no structure; **Rent This Moon** for admins or applicants.

## Permissions

Assign via Alliance Auth groups (Django permission strings):

| Permission | Codename | Who |
|------------|----------|-----|
| View leases & available moons | `moonrentals.view_leases` | Members, renters, leadership |
| Apply to rent | `moonrentals.apply_rent` | Renters |
| Full admin | `moonrentals.admin_management` | Moon/rental admins |

## Installation

1. Ensure **`moonmining`** is installed and migrated.

2. Add the rentals app to `INSTALLED_APPS`:

```python
INSTALLED_APPS = [
    # ...
    "moonmining",
    "moonmining.rentals.apps.MoonRentalsConfig",
]
```

3. Run migrations:

```bash
python manage.py migrate moonrentals
```

4. Add Celery beat entries (adjust intervals as needed):

```python
from django_celery_beat.schedules import crontab

CELERYBEAT_SCHEDULE["moonrentals_poll_wallet_payments"] = {
    "task": "moonmining.rentals.tasks.poll_rental_wallet_payments",
    "schedule": crontab(minute="*/30"),
}
CELERYBEAT_SCHEDULE["moonrentals_sync_fuel_from_structures"] = {
    "task": "moonmining.rentals.tasks.sync_rental_fuel_from_structures",
    "schedule": crontab(minute=45, hour="*/1"),
}
CELERYBEAT_SCHEDULE["moonrentals_check_fuel_alerts"] = {
    "task": "moonmining.rentals.tasks.check_rental_fuel_alerts",
    "schedule": crontab(minute=15, hour="*/2"),
}
```

5. **Wallet ESI scopes** on your corp accountant token (CCP application + character token):

- `esi-wallet.read_corporation_wallets.v1`
- `esi-corporations.read_divisions.v1`

6. Optional: install **[aa-structures](https://apps.allianceauth.org/apps/detail/aa-structures)** for automatic fuel % sync.

7. Grant permissions to groups in Auth admin → assign `moonrentals.*` permissions.

8. Open **Renter Management → Settings** (gear): set corp ID, wallet division, payment keyword (default `MOON-RENT-REVENUE`), webhook URLs, and optionally enable **Auto-approve applications**.

## Admin settings (database)

Configured in the UI (**Settings** gear on Renter Management). Stored in `RentalModuleSettings` (singleton).

| Field | Purpose |
|-------|---------|
| Corporation ID | Corp whose wallet journal is polled |
| Wallet division | Corp wallet division 1–7 |
| Payment keyword | Substring required in journal description |
| Due day of month | Calendar day rent is due (1–28) |
| Grace period days | Days after due before **overdue** |
| Fuel alert threshold % | Discord fuel webhook when fuel falls below |
| Fuel reference hours | Hours of fuel treated as 100% (default 720) |
| Fuel / payment webhook URLs | Discord incoming webhooks |
| ESI token ID | Optional django-esi `Token` PK override |
| Auto-approve applications | Create lease immediately on renter apply |

## Payment matching

Each lease gets a reference string:

```text
MOON-RENT-REVENUE <system> - <moon name>
```

Renters should use this exact text (or contain the keyword + location) when paying corp wallet. The poll task marks the lease **Paid** when journal amount ≥ monthly rent.

## Fuel percentage

When **aa-structures** is installed, fuel % is:

```text
percent = min(100, round(hours_fuel_expires / fuel_reference_hours * 100))
```

Synced hourly and on lease save. Manual override remains on the lease form.

## REST API

OpenAPI sketch: `moonmining/rentals/openapi.yaml`.

| Method | Path | Permission |
|--------|------|------------|
| GET | `/moonmining/api/rentals/leases` | `view_leases` |
| POST | `/moonmining/api/rentals/leases` | `admin_management` or `apply_rent` |
| GET/PUT | `/moonmining/api/rentals/config` | `admin_management` |
| POST | `/moonmining/api/rentals/leases/<id>/evict` | `admin_management` |
| GET | `/moonmining/api/rentals/users?q=` | `admin_management` (POC search) |

## Celery tasks

| Task | Purpose |
|------|---------|
| `moonmining.rentals.tasks.poll_rental_wallet_payments` | Wallet journal → mark paid |
| `moonmining.rentals.tasks.sync_rental_fuel_from_structures` | Update lease fuel % from structures |
| `moonmining.rentals.tasks.check_rental_fuel_alerts` | Sync fuel + send low-fuel Discord webhooks |

## EvE-EMU deployment

In the **eve-emu** Docker stack, this module is copied from `deploy/aa_docker/patches/moonmining/rentals/` into the image. See `docs/ALLIANCE_AUTH.md` in the eve-emu repository for compose commands and environment variables (`AA_MOONRENTALS_WALLET_POLL_MINUTES`, etc.).

## Relation to other apps

- **aa-moonmining** — moon surveys, refineries, extractions (required).
- **aa-structures** — fuel expiry for fuel % (recommended).
- **moon_rentals** (eve-emu only) — separate app for **moon pop schedule** and buyback compliance; not the same as this lease module.
