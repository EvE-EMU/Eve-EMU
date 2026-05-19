# Corp stock orders (`corp_orders`)

Alliance Auth plugin at **`https://auth.<domain>/corp-orders/`** for officer/director **item exchange** purchase contracts (corp stock buys with delivery).

## Pricing

- **Items:** Janice Jita **sell** + configurable markup (default **10%**).
- **Freight:** [PushX API](https://api.pushx.net/api/quote/) from **Jita** → **Badivefi** (hub; configurable in admin). Officers enter a **final destination system** on the form for tracking; pricing always uses the hub route.
  - Volume ≤ **360,000 m³:** PushX `PriceNormal`.
  - Volume > **360,000 m³:** average of PushX and Rhea fuel (140,000 × Nitrogen Isotopes Jita sell), **capped at PushX**.
- **Speed surcharge** on (items + freight):
  - **God Speed** (6h): +25%
  - **Alter Speed** (66h): +15%
  - **Regular** (7 days): no surcharge

Contract: **I will pay** = total; **I will receive** = 0. Description includes speed label and unique code (`ORD-XXXXXXXX`).

**Discord (new order webhook)** includes contract fields (pay amount, description, expiration, assignee), the full item list, final destination, and freight route.

**Performance:** Janice prices are batched (DB cache + parallel API); create reuses the last calculated quote from session; Discord notify runs on Celery.

## Setup

1. **Janice** (same as buyback): `BUYBACKPROGRAM_PRICE_METHOD=Janice` and `BUYBACKPROGRAM_PRICE_JANICE_API_KEY` in `.env`.
2. **Discord webhooks** (optional):
   ```env
   CORP_ORDERS_NEW_CONTRACT_WEBHOOK=https://discord.com/api/webhooks/...
   CORP_ORDERS_PAYBACK_WEBHOOK=https://discord.com/api/webhooks/...
   CORP_ORDERS_PUSHX_CLIENT=eve-emu
   ```
3. Rebuild **`aa-web`** / **`aa-worker`** and migrate:
   ```bash
   docker compose build aa-web aa-worker aa-beat
   docker compose up -d aa-web aa-worker aa-beat
   docker compose exec aa-web python manage.py migrate corp_orders
   docker compose exec aa-web python manage.py corp_orders_grant_officers
   ```
   Defaults to groups **Directors** and **Officers** (override with `--group Name` or `CORP_ORDERS_GRANT_GROUPS=Directors,Officers` in `.env`).
4. Django admin → **Corp orders configuration** — adjust systems, thresholds, multipliers.

## Permissions

| Permission | Use |
|------------|-----|
| `corp_orders.create_order` | Create quotes/orders |
| `corp_orders.create_corp_contract` | Issue as **corporation** contract (corp wallet) |
| `corp_orders.manage_orders` | View all users' orders; cancel open orders |

## Workflow

1. **Corp stock orders** → paste inventory → **Calculate quote** → **Create order**.
2. Follow in-game steps on the order detail page (ESI does not create item exchange contracts via API).
3. Paste the **EVE contract ID** to link tracking.
4. Celery polls contract status; **payback** webhook fires when complete if personal wallet + payback enabled.

Managers with **manage orders** can **Cancel order** on the detail page (or bulk-cancel in Django admin) for any order not yet completed.

## Notes

- PushX rate limit: ~100 calls per 10 minutes — avoid spamming quotes.
- Officers need `esi-contracts.read_character_contracts.v1` on their token for status polling.
