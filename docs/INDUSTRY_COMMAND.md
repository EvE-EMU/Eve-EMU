# Industry Command — how the four industry systems fit together

Four separate systems now do "industry" in this stack: **Auth Indy Hub**
(third-party), **`mfg_projects`** (this repo's own Industry Command Center),
**`freight_bridge`** (this repo's own freight service), and **`penguin_bridge`**
(this repo's bridge to the EVE-Penguin desktop client). They were built at
different times, own different data, and — this is the part that isn't
obvious from any one of them alone — two different, *incompatible* session
systems gate who can call what. This doc is the map that was missing when
EVE-Penguin's Industry Calculator (2026-09-13) needed to figure out which of
the four to build against, and why.

## The four systems, in one table

| System | What it is | Where it lives | Owns |
|---|---|---|---|
| **Indy Hub** | Real, installed third-party AA app (`indy-hub==1.18.3` on PyPI) | `.tmp_indy_hub` unpacked for reference; the live install is the pip package, patched by `deploy/aa_docker/indy_hub_*.py` | Blueprints, industry jobs, **`IndustryStructure`/`IndustryStructureRig`** (real structure/rig registry, ESI-synced), **`ProductionProject`/`ProductionProjectItem`** ("Crafting Projects" — a *personal* build-list feature), copy requests, material exchange |
| **`mfg_projects`** | This repo's own Django app — a much larger Industry Command Center | `deploy/aa_docker/mfg_projects/` | Project board, quotes (requester ↔ builder), a builder/buyer workbench, wallet/P&L matching (`services/wallet.py`, `services/pnl.py`), an "advisor" (`mfg_advisor_api.py`) — reads *through* to Indy Hub's `ProductionProject` for some of this |
| **`freight_bridge`** | This repo's own real freight-pricing/booking service | `deploy/aa_docker/freight_bridge/` | Freight rate tables, `calculate_quote()` (the actual pricing engine — SLYCE mesh routing, hauling classes, coupons/discounts), quote tokens, the freight web app's own login |
| **`penguin_bridge`** | The bridge for the EVE-Penguin **desktop** client | `deploy/aa_docker/penguin_bridge/` | Nothing of its own except client-facing glue: ESI proxying, fittings, wormhole map, pings, and (new 2026-09-13) **structures**, **freight quotes**, **projects**, **jobs** — all thin wrappers calling *into* the other three, not separate data stores (except `PenguinBuildJob`, below) |

## The auth boundary — the one thing to know before touching any of this

`mfg_projects` and `freight_bridge` both sit behind **`freight_bridge`'s own
session system** (`freight_bridge.services.session.verify_session()`,
checked via `X-Freight-Session`/`X-Mfg-Session` headers or a `session` query
param) — a login built for the eve-emu.com **web app**, with its own
director/role derivation (`mfg_public_api.py`'s `derive_portal_flags()`).

`penguin_bridge` has a **completely separate** session (a stateless HMAC
token, `penguin_bridge/session.py`, issued via the desktop client's
loopback-redirect login). These two do not know about each other.

This means: **any `mfg_projects`/`freight_bridge` endpoint that needs
`_require_director`/`_require_craft_access`/`_session()` is unreachable from
`penguin_bridge` today.** That's a real, deliberate gap — not a bug. Bridging
it needs a new endpoint that mints a `freight_bridge`-compatible session
from an already-verified `penguin_bridge` one, through the same
loopback-redirect pattern `penguin_bridge.authorize` already uses for its
own login. **Not built as of 2026-09-13** — real, scoped follow-up work,
tracked as the highest-leverage item in the platform improvement plan (it
unlocks all of `mfg_projects`' project board/quotes/workbench for both
EVE-Penguin and any future core-web UI at once).

### The shortcut that unblocked EVE-Penguin anyway

Not everything needed that bridge. Two things that look like they should
need it, don't:

- **`list_auth_structures()`** (`mfg_projects/services/craft/structures.py`)
  only touches Indy Hub's `IndustryStructure`/`IndustryStructureRig` models
  via plain Django ORM — no `freight_bridge` session required. `penguin_bridge`
  calls it directly (`penguin_bridge/industry.py`), gated instead by
  `user_in_false_gods()`.
- **Indy Hub's `ProductionProject`** only needs a Django `User` to read/write
  — again, no `freight_bridge` session. `penguin_bridge/projects.py` reads
  and writes it directly via ORM, gated by Indy Hub's own real permission
  (`user.has_perm("indy_hub.can_access_indy_hub")`).

The rule of thumb: **if the thing you need is a model, reach it directly by
ORM and gate it with a real permission check; only the `mfg_projects`/
`freight_bridge` *views* — the project board, quotes, the pricing engine —
are behind the separate session.** `calculate_quote()`
(`freight_bridge/services/pricing.py`) is the one exception — it's a
function, not a gated view, so `penguin_bridge/industry.py` calls it
directly too (`audit=False, mint_token=False` — a price estimate, not a
booking).

## What's new, and why it's a new model

**`PenguinBuildJob`** (`penguin_bridge/models.py`, migration `0005`) is a
genuinely new, `penguin_bridge`-owned model — not another use of Indy Hub's
`ProductionProject`. Indy Hub's model is personal (one `User` FK, no shared
board); this needed a **shared, org-scoped job board** with a mode
(corp/divisional), a tier (D0–D3), and a claim/deliver lifecycle Indy Hub has
no concept of. Gated the same shape Indy Hub gates itself
(`default_permissions=()` + a custom `can_manage_build_jobs` permission),
independently grantable — not tied to any "director" flag from the
`freight_bridge` session system.

## Quick reference — what calls what

```
EVE-Penguin (desktop)
  │  penguin_bridge session (HMAC token)
  ▼
penguin_bridge/
  ├─ industry.py    → mfg_projects.services.craft.structures  (ORM, no ff_bridge session)
  │                 → freight_bridge.services.pricing.calculate_quote()  (function call)
  ├─ projects.py     → indy_hub.models.ProductionProject       (ORM, indy_hub's own permission)
  └─ jobs.py         → penguin_bridge.models.PenguinBuildJob   (owns this one)

core-web (eve-emu.com) — NOT YET WIRED to any of penguin_bridge's endpoints
  │  freight_bridge session (separate system)
  ▼
mfg_public_api.py / mfg_industry_api.py / mfg_divisional_api.py / mfg_advisor_api.py
  → mfg_projects/, freight_bridge/  (the full project board, quotes, workbench, advisor)
```

## Real gaps, tracked, not silently assumed away

- **core-web has no UI yet for `/penguin/structures`, `/penguin/freight/*`,
  `/penguin/projects`, or `/penguin/jobs`.** It has its own, older, larger
  system (`mfg_projects`) instead — the two don't share a UI today.
- **The `freight_bridge` auth bridge** (above) — the single highest-leverage
  piece of remaining work; it would let EVE-Penguin (and a future core-web
  UI) reach the *entire* existing project board/quote/workbench, not just
  the ORM-reachable slice.
- **D0 auto-restock** (`PenguinBuildJob.source_kind = "auto_restock"`) has no
  automation behind it yet — needs a real corp minimum-inventory/market-level
  tracker, likely built on `market-tools/`'s existing price data.
- **Margin-split payouts** (`PenguinBuildJob.builder_share_isk`/
  `corp_share_isk`) are computed and stored, not paid — `mfg_projects/
  services/wallet.py` and `services/pnl.py` already do ESI wallet-transaction
  matching for the older project system; wiring a delivered `PenguinBuildJob`
  to that is real follow-up work.
