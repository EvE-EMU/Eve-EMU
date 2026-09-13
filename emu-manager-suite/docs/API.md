# EMU Manager Suite — API

Base URL: `https://emums.eve-emu.com/v1`

OpenAPI UI: `https://emums.eve-emu.com/docs`

## Authentication

All endpoints except health require header:

```
X-EMUMS-Key: <EMUMS_API_KEY>
```

Default test key: `emums-dev-key-change-me` (override in `.env.test`).

## Endpoints

### Health

| Method | Path | Auth | Description |
|--------|------|------|-------------|
| GET | `/v1/health` | No | Liveness + version |

### Dashboard

| Method | Path | Description |
|--------|------|-------------|
| GET | `/v1/dashboard` | KPIs, chart series, recent invoices |

### Settings

| Method | Path | Description |
|--------|------|-------------|
| GET | `/v1/settings` | Org configuration |
| PATCH | `/v1/settings` | Partial update |

### Moons (forked domain)

| Method | Path | Description |
|--------|------|-------------|
| GET | `/v1/moons/mining-logs` | Observer log rows (`limit`, `offset`) |
| GET | `/v1/moons/invoices` | Tax invoices (`status` filter) |
| GET | `/v1/moons/tax-rules` | Structure tax rule list |

### Templates

| Method | Path | Description |
|--------|------|-------------|
| GET | `/v1/templates` | List templates |
| POST | `/v1/templates` | Create |
| GET | `/v1/templates/{id}` | Get one |
| PATCH | `/v1/templates/{id}` | Update |
| POST | `/v1/templates/{id}/render` | Jinja2 render preview |
| GET | `/v1/templates/{id}/variables` | Declared variable names |

## Error shape

FastAPI default:

```json
{ "detail": "Human-readable message" }
```

## Example

```bash
curl -s -H "X-EMUMS-Key: emums-dev-key-change-me" \
  https://emums.eve-emu.com/v1/dashboard | jq .tagline
```
