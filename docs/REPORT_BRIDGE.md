# Report bridge: webhooks + DB export + ESI

Three channels for **The Great Damn EMU Report** — use all three for “all information” without sharing AA database credentials.

| Channel | Repo | Direction | Purpose |
|---------|------|-----------|---------|
| **ESI** | [aa-esi-forwarder](../repos/aa-esi-forwarder/) | Report → AA → ESI | Live corp wallets, assets, etc. (token scopes) |
| **Webhooks** | [aa-report-bridge](../repos/aa-report-bridge/) | AA → Report | Push on change (users, groups, characters, mining tax, …) |
| **Export API** | [aa-report-bridge](../repos/aa-report-bridge/) | Report → AA | Historical backfill into report SQLite |

## 1. On Alliance Auth (each corp that shares data)

Install both plugins and set env (example for home corp):

```env
ESI_FORWARDER_API_KEYS=emu-report:SECRET_A
ESI_FORWARDER_DEFAULT_TOKEN_ID=58

REPORT_BRIDGE_API_KEYS=emu-report:SECRET_A
REPORT_BRIDGE_SITE_ID=eve-emu
REPORT_BRIDGE_WEBHOOK_URL=https://report.eve-emu.com/v1/ingest/home
REPORT_BRIDGE_WEBHOOK_SECRET=SECRET_B
```

Caddy (auth host):

```caddyfile
handle /internal/esi-forwarder/* {
    reverse_proxy aa-web:8080
}
handle /internal/report-bridge/* {
    reverse_proxy aa-web:8080
}
```

`INSTALLED_APPS` (eve-emu `deploy/aa_docker/extensions/apps.py` when you wire it):

```python
"aa_esi_forwarder.apps.AaEsiForwarderConfig",
"aa_report_bridge.apps.AaReportBridgeConfig",
```

Copy `repos/aa-report-bridge/aa_report_bridge` into the AA image (same as esi-forwarder).

## 2. On Great Damn EMU Report

`data/connections.json`:

```json
{
  "id": "home",
  "label": "False Gods",
  "forwarder_url": "https://auth.eve-emu.com",
  "secret": "SECRET_A",
  "webhook_secret": "SECRET_B",
  "default_token_id": 58,
  "enabled": true
}
```

- `secret` — ESI forwarder + export API (`X-Report-Bridge-Secret`)
- `webhook_secret` — must match AA `REPORT_BRIDGE_WEBHOOK_SECRET`
- Ingest URL on AA must use the same link id: `/v1/ingest/home`

## 3. Operations

**Test links**

```bash
curl -X POST https://report.eve-emu.com/v1/links/home/test
```

**Initial historical load** (pulls AA DB snapshots into report SQLite):

```bash
curl -X POST https://report.eve-emu.com/v1/links/home/sync/export \
  -H "Content-Type: application/json" \
  -d '{"resource": "auth.user"}'

curl -X POST ... -d '{"resource": "auth.group"}'
curl -X POST ... -d '{"resource": "eveonline.evecharacter"}'
curl -X POST ... -d '{"resource": "miningtaxes.character"}'
```

**Query stored history** (webhooks + export rows):

```bash
curl "https://report.eve-emu.com/v1/links/home/history?model=auth.user&limit=50"
```

**Live ESI** (unchanged):

```bash
curl -X POST https://report.eve-emu.com/v1/links/home/reports/corp-snapshot \
  -H "Content-Type: application/json" \
  -d '{"corporation_id": 98799892, "include_wallets": true}'
```

**Test webhook from AA**

```bash
curl -X POST https://auth.eve-emu.com/internal/report-bridge/v1/webhooks/test/ \
  -H "X-Report-Bridge-Secret: SECRET_A"
```

## 4. Docker compose (report service)

```yaml
  emu-report:
    build:
      context: ./repos
      dockerfile: great-damn-emu-report/Dockerfile
    volumes:
      - ./repos/great-damn-emu-report/data:/app/data
    environment:
      REPORT_CONNECTIONS_FILE: /app/data/connections.json
      REPORT_HISTORY_DB: /app/data/history/events.sqlite
      REPORT_ADMIN_API_KEY: ${EMU_REPORT_ADMIN_KEY}
    expose: ["8020"]
```

Put auth in front of port 8020; ingest URL is public only if you rely on HMAC (`webhook_secret`).

## 5. Adding corp-specific tables

Edit `repos/aa-report-bridge/aa_report_bridge/exporters.py`:

- Register a new resource in `EXPORTERS`
- Add model to `REPORT_BRIDGE_WATCH_MODELS` on AA

Redeploy AA + run one `sync/export` for that resource.

## Security

- Do not expose AA admin or Postgres.
- Rotate `emu-report:…` keys independently on each AA site.
- Use `REPORT_BRIDGE_ALLOWED_IPS` / `ESI_FORWARDER_ALLOWED_IPS` for stable report server IPs.
- `webhook_secret` is only for HMAC verification of inbound POSTs.
