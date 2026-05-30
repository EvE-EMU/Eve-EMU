# The Great Damn EMU Report

Reporting API across **multiple Alliance Auth 5** sites with three data channels:

| Channel | AA plugin | Report endpoints |
|---------|-----------|------------------|
| **ESI (live)** | [aa-esi-forwarder](../aa-esi-forwarder/) | `GET/POST /v1/links/{id}/character/…`, `reports/corp-snapshot` |
| **Webhooks (live DB changes)** | [aa-report-bridge](../aa-report-bridge/) | `POST /v1/ingest/{id}` |
| **Export (historical backfill)** | [aa-report-bridge](../aa-report-bridge/) | `POST /v1/links/{id}/sync/export`, `GET …/history` |

No AA database credentials on the report host. Historical rows are stored locally in SQLite (`REPORT_HISTORY_DB`).

## Quick start (home + external AA)

### On their AA5

1. Install **aa-esi-forwarder** + **aa-report-bridge**.
2. Set keys and webhook target (link id must match your `connections.json` `id`):

```env
ESI_FORWARDER_API_KEYS=emu-report:SECRET_A
REPORT_BRIDGE_API_KEYS=emu-report:SECRET_A
REPORT_BRIDGE_WEBHOOK_URL=https://report.yoursite.com/v1/ingest/allied-corp
REPORT_BRIDGE_WEBHOOK_SECRET=SECRET_B
REPORT_BRIDGE_SITE_ID=allied-corp
```

3. Expose `/internal/esi-forwarder/*` and `/internal/report-bridge/*` on HTTPS.

### On this service

```json
{
  "id": "allied-corp",
  "label": "Friend alliance",
  "forwarder_url": "https://auth.their-site.com",
  "secret": "SECRET_A",
  "webhook_secret": "SECRET_B",
  "default_token_id": 12,
  "enabled": true
}
```

```bash
# Test ESI + export API
curl -X POST https://report.yoursite.com/v1/links/allied-corp/test

# Backfill users/groups/characters into local history DB
curl -X POST https://report.yoursite.com/v1/links/allied-corp/sync/export \
  -H "Content-Type: application/json" \
  -d '{"resource": "auth.user"}'

# Query stored events (webhooks + exports)
curl "https://report.yoursite.com/v1/links/allied-corp/history?limit=100"
```

## Run locally

```bash
cp .env.example .env
cp connections.example.json data/connections.json
pip install -r requirements.txt
uvicorn report_app.main:app --port 8020
```

## API overview

| Path | Description |
|------|-------------|
| `GET /v1/links` | Registered AA links |
| `POST /v1/links/{id}/test` | Ping forwarder + report-bridge |
| `POST /v1/ingest/{id}` | **Inbound webhooks** from AA (HMAC) |
| `GET /v1/links/{id}/history` | Query local event store |
| `POST /v1/links/{id}/sync/export` | Pull paginated AA export into history |
| `GET /v1/links/{id}/character/{id}` | ESI via forwarder |
| `POST /v1/links/{id}/reports/corp-snapshot` | Corp report via ESI |

Full deploy notes: [docs/REPORT_BRIDGE.md](../../docs/REPORT_BRIDGE.md)

## Environment

| Variable | Purpose |
|----------|---------|
| `REPORT_CONNECTIONS_FILE` | Links JSON |
| `REPORT_HISTORY_DB` | SQLite path for webhooks + exports |
| `REPORT_ADMIN_API_KEY` | Protects `POST/DELETE /v1/admin/links` |

## Docker

```bash
docker build -f repos/great-damn-emu-report/Dockerfile -t emu-report repos
docker run --rm -p 8020:8020 -v ./data:/app/data emu-report
```

## Security

- `webhook_secret` verifies `X-Report-Webhook-Signature` on ingest.
- Put the report API behind VPN or reverse-proxy auth; ingest relies on HMAC if exposed.
- Each AA site rotates its own API keys.
