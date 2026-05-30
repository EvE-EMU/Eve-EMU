# AA ESI Forwarder

Alliance Auth 5 plugin + Python client so **trusted external services** (e.g. [The Great Damn EMU Report](../great-damn-emu-report/)) can use your corp’s **django-esi** tokens without sharing refresh tokens or AA database access.

Works **inside Docker** (`http://aa-web:8080`) and **across the internet** (`https://auth.their-corp.com`) when you expose the forwarder paths over HTTPS with an API key.

## Architecture

```
EVE ESI  ←——  Their AA5 (django-esi)  ←——  aa-esi-forwarder on their auth site
                                              ↑ HTTPS + API key
                                    Great Damn EMU Report (your reporting host)
```

## Install on Alliance Auth 5 (any deployment)

1. Install package / copy `aa_esi_forwarder` into the AA image.
2. `INSTALLED_APPS += ["aa_esi_forwarder.apps.AaEsiForwarderConfig"]`
3. Configure environment:

```env
# One key per consumer (recommended for external links)
ESI_FORWARDER_API_KEYS=emu-report:LONG_RANDOM_SECRET_HERE,backup:OTHER_SECRET

# Or legacy single secret (still works)
# ESI_FORWARDER_INTERNAL_SECRET=LONG_RANDOM_SECRET

ESI_FORWARDER_DEFAULT_TOKEN_ID=58
# Optional: require scopes on that token
# ESI_FORWARDER_REQUIRED_SCOPES=esi-wallet.read_corporation_wallets.v1

# Optional: only allow Great Damn EMU Report server IP(s)
# ESI_FORWARDER_ALLOWED_IPS=203.0.113.10/32,198.51.100.0/24

ESI_FORWARDER_COMPATIBILITY_DATE=2025-12-16
ESI_FORWARDER_USER_AGENT=TheirCorp-AA-Forwarder/1.0
```

4. Expose **only** these paths on your public auth URL (Caddy/nginx):

- `/internal/esi-forwarder/v1/health/`
- `/internal/esi-forwarder/v1/token/`
- `/internal/esi-forwarder/v1/proxy/*`

Example Caddy snippet (auth host):

```caddyfile
handle /internal/esi-forwarder/* {
    reverse_proxy aa-web:8080
}
```

5. Give the reporting operator:

| Share | Example |
|-------|---------|
| Forwarder base URL | `https://auth.your-corp.com` |
| API key | the `emu-report:…` secret value |
| Default token id | django-esi pk with needed scopes |

They **never** need your AA admin login.

## API (consumer → your AA)

| Endpoint | Purpose |
|----------|---------|
| `GET …/health/` | Test link (no ESI traffic) |
| `GET …/token/?token_id=58` | Short-lived access token (optional) |
| `GET\|POST …/proxy/latest/{esi_path}` | ESI call with your token attached |

Auth headers (either):

- `X-Esi-Forwarder-Secret: <api-key>`
- `Authorization: Bearer <api-key>`

## Python client

```python
from esi_forwarder_client import EsiForwarderClient

client = EsiForwarderClient(
    base_url="https://auth.your-corp.com",
    secret="LONG_RANDOM_SECRET",
)
print(client.ping())
status, data, _ = client.esi_get("corporations/98799892/")
```

## Security checklist (external)

- Use **HTTPS** only on the public auth hostname.
- Use a **long random API key** per consumer (`ESI_FORWARDER_API_KEYS`).
- Set **`ESI_FORWARDER_ALLOWED_IPS`** to the reporting server if its IP is stable.
- Do **not** expose AA admin, GraphQL, or other `/internal/*` routes.
- Rotate keys by adding a new `consumer_id:secret` and removing the old one.

## Related

- [Great Damn EMU Report](../great-damn-emu-report/) — registers multiple `links` to different AA5 forwarders.
- eve-emu `market_bridge` — older single-purpose bridge for market-tools only.
