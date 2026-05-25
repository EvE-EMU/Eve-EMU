# YouTrack (`pm.<DOMAIN_NAME>`)

[JetBrains YouTrack](https://www.jetbrains.com/youtrack/) runs at **`https://pm.eve-emu.com`** (or `https://pm.<DOMAIN_NAME>`). Sign-in uses **Alliance Auth** as an OpenID Connect provider, so users log in with the same **EVE SSO** flow as `auth.eve-emu.com`, restricted to members of the **Project Manager** Django auth group.

## Stack note (Linux vs Windows image)

The Compose service uses the official **[`jetbrains/youtrack`](https://hub.docker.com/r/jetbrains/youtrack/)** image (Linux), which matches the rest of the eve-emu stack. The **[`jetbrains/youtrack-windows`](https://hub.docker.com/r/jetbrains/youtrack-windows/tags/)** image is **Windows containers only** and is not used here.

Pin the build in `.env`:

```env
YOUTRACK_VERSION=2026.1.13570
YOUTRACK_URL=https://pm.eve-emu.com
```

## Architecture

| Component | Role |
|-----------|------|
| `youtrack` | YouTrack on port 8080 (persistent volumes for data/conf/logs/backups) |
| `pm.<DOMAIN_NAME>` | Public URL (Caddy TLS) |
| `auth.<DOMAIN_NAME>/o/` | OIDC provider ([allianceauth-oidc-provider](https://github.com/Solar-Helix-Independent-Transport/allianceauth-oidc-provider)) |
| EVE SSO | Users authenticate to Alliance Auth first; OIDC only issues tokens to allowed groups |

## DNS

Add **`pm.eve-emu.com`** (or `pm.<DOMAIN_NAME>`) to the same host as Caddy (A/AAAA record).

## Deploy

```powershell
docker compose build aa-web aa-worker
docker compose up -d youtrack caddy aa-web aa-worker
```

On first `aa-web` boot, an OIDC RSA key is created at `/app/site/oidc/oidc_rsa.pem` inside the container (persisted on the `eve_emu_aa_site` volume if you mount one; otherwise regenerated on rebuild — set `AA_OIDC_RSA_PRIVATE_KEY` in `.env` to keep a stable key).

## 1. Alliance Auth — Project Manager group

1. **Django Admin** → **Authentication and Authorization** → **Groups** → add group **`Project Manager`** (name must match `AA_YOUTRACK_OIDC_ALLOWED_GROUPS` in `.env`).
2. Add each user who should access YouTrack to that group.
3. Grant **`allianceauth_oidc | alliance auth application | Can access oidc`** (`access_oidc`) to those users (via group permissions or state).

Users still log in to Alliance Auth with **EVE SSO** as usual; the OIDC app only gates *which Auth accounts* may authorize YouTrack.

## 2. Alliance Auth — OIDC application

1. Open **`https://auth.eve-emu.com/admin/allianceauth_oidc/`** (or **OAuth2_provider** applications, depending on admin labels).
2. **Add application**:
   - **Client type:** Confidential
   - **Authorization grant type:** Authorization code
   - **Algorithm:** RSA with SHA-2 256
   - **Redirect URIs:** copy from YouTrack after step 3 (Hub auth module redirect URI), e.g.  
     `https://pm.eve-emu.com/hub/auth/oauth2/callback` (exact path comes from YouTrack).
3. Under **Groups** (application access), allow **`Project Manager`** only (or your configured group name).
4. Save **Client ID** and **Client secret** (copy secret before save if hashed).

Optional `.env` (documentation only — secrets stay in YouTrack/AA admin):

```env
AA_OIDC_ENABLED=1
AA_YOUTRACK_OIDC_ALLOWED_GROUPS=Project Manager
```

## 3. YouTrack — first-time setup

1. Open **`https://pm.eve-emu.com`**.
2. If this is a new install, complete the **Configuration Wizard** (get `wizard_token` from container logs: `docker compose logs youtrack`).
3. Set **Base URL** to **`https://pm.eve-emu.com`** (must match Caddy and `YOUTRACK_URL`).
4. **Application listen port:** **`8080`** (HTTP inside the container). **Do not** enable built-in TLS / **8443** when using Caddy — Caddy already serves `https://pm.eve-emu.com` on 443 and forwards to `youtrack:8080`.

## 4. YouTrack — OpenID Connect (Alliance Auth)

In YouTrack: **Administration → Access Management → Auth Modules** → add **OpenID Connect** ([docs](https://www.jetbrains.com/help/youtrack/server/openid-connect-authentication-module.html)).

| Setting | Value |
|---------|--------|
| OIDC / Issuer URL | `https://auth.eve-emu.com/o/` |
| Authorization endpoint | `https://auth.eve-emu.com/o/authorize/` |
| Token endpoint | `https://auth.eve-emu.com/o/token/` |
| User info | `https://auth.eve-emu.com/o/userinfo/` |
| JWKS (if shown) | `https://auth.eve-emu.com/o/.well-known/jwks.json` |
| Client ID / Secret | From Alliance Auth OIDC application |
| **Scopes** | **`openid profile email`** only (see below if you get `invalid_scope`) |

**Attribute Mapping** tab ([docs](https://www.jetbrains.com/help/youtrack/server/openid-connect-authentication-module.html)):

| YouTrack field | Claim |
|----------------|--------|
| User identifier claim | `sub` |
| **User name claim** | **`name`** (or `preferred_username`) — Alliance Auth main character |
| Email claim | `email` |
| Full name claim | `name` (optional) |
| Groups claim | `groups` (optional; map **Project Manager** to YouTrack roles if desired) |

Alliance Auth sends **`name`**, **`preferred_username`**, and **`nickname`** as the main character name. If YouTrack shows the email local-part instead, set **User name claim** to `name` and log in again. Existing accounts keep their old username until an admin renames them or the user is re-provisioned.

**Scopes field:** use exactly `openid profile email` (space-separated, no `groups` in the scope list). Group data still arrives via the **`profile`** scope (`groups` claim). If YouTrack or Hub sends extra scopes, rebuild `aa-web` after the OIDC scope patch in `oidc_provider.py`.

Register YouTrack’s **redirect URI** in the Alliance Auth application redirect list.

Enable the module and disable guest login if you want SSO-only access.

## 5. Verify

1. Log out of YouTrack.
2. Open **`https://pm.eve-emu.com`** → sign in via OIDC → you should be sent to **`https://auth.eve-emu.com`** (EVE SSO if not already logged in).
3. A user **without** the Project Manager group should be denied at the OIDC authorize step.

## Optional: built-in HTTPS keystore (JKS / PKCS#12)

If you enable **HTTPS inside YouTrack** (port 8443) instead of terminating TLS only at Caddy, generate a self-signed keystore:

**PowerShell (Windows):**

```powershell
cd deploy\youtrack\keystore
powershell -NoProfile -ExecutionPolicy Bypass -File .\generate-keystore.ps1
# Custom CN / password:
powershell -NoProfile -ExecutionPolicy Bypass -File .\generate-keystore.ps1 -Cn pm.eve-emu.com -StorePass "your-secret"
```

**Bash:**

```bash
cd deploy/youtrack/keystore
chmod +x generate-keystore.sh
./generate-keystore.sh pm.eve-emu.com
```

Outputs (gitignored):

| File | Format |
|------|--------|
| `deploy/youtrack/keystore/youtrack.p12` | PKCS#12 |
| `deploy/youtrack/keystore/youtrack.jks` | JKS |

- **Alias:** `youtrack`
- **Default store password:** `change-me` (override with `-StorePass` or `YOUTRACK_KEYSTORE_PASSWORD`)
- **CN / SAN:** `pm.eve-emu.com`, `localhost`, `127.0.0.1`

Verify:

```powershell
keytool -list -keystore deploy\youtrack\keystore\youtrack.p12 -storetype PKCS12 -storepass change-me
```

Copy into the container if needed:

```powershell
docker compose cp deploy/youtrack/keystore/youtrack.p12 youtrack:/opt/youtrack/conf/youtrack.p12
```

In the YouTrack Configuration Wizard or **TLS** settings, choose PKCS#12 or JKS and point at that path. For production, replace the self-signed cert with one from your CA or use Caddy-only TLS (recommended).

**One-liner without the script:**

```powershell
keytool -genkeypair -alias youtrack -keyalg RSA -keysize 2048 -validity 3650 `
  -storetype PKCS12 -keystore youtrack.p12 -storepass change-me -keypass change-me `
  -dname "CN=pm.eve-emu.com, OU=EVE-EMU, O=EVE-EMU, C=US" `
  -ext "SAN=dns:pm.eve-emu.com,dns:localhost,ip:127.0.0.1"
```

## Troubleshooting

### “Listen port 8443” / service not accessible in browser

You enabled **HTTPS inside YouTrack (8443)**, but Compose only exposes **8080** and Caddy proxies to **HTTP 8080**. Users hit `https://pm.eve-emu.com:443` → Caddy → `youtrack:8080`, not 8443.

**Fix (recommended):** switch YouTrack back to HTTP **8080**, keep **Base URL** `https://pm.eve-emu.com`:

```powershell
deploy\youtrack\fix-listen-port-8080.cmd
```

Or if PowerShell blocks `.ps1` scripts:

```powershell
powershell -NoProfile -ExecutionPolicy Bypass -File deploy\youtrack\fix-listen-port-8080.ps1
```

Or manually ([JetBrains reverse proxy docs](https://www.jetbrains.com/help/youtrack/server/reverse-proxy-configuration.html)):

```powershell
docker compose stop youtrack
docker run --rm -v eve-emu_eve_emu_youtrack_conf:/opt/youtrack/conf jetbrains/youtrack:2026.1.13570 configure --listen-port=8080 --base-url=https://pm.eve-emu.com
docker compose up -d youtrack
```

(Volume name may be `eve_emu_youtrack_conf` — check `docker volume ls | Select-String youtrack`.)

**Wizard settings (behind Caddy):**

| Setting | Value |
|---------|--------|
| Base URL | `https://pm.eve-emu.com` |
| Application listen port | `8080` |
| Built-in TLS | **Off** (no keystore / no 8443) |

| Symptom | Check |
|---------|--------|
| 502 on `pm.*` | `docker compose ps youtrack`; `docker compose logs youtrack` |
| 8443 / not accessible | Re-run `fix-listen-port-8080.ps1`; Caddy uses port **8080** only |
| OIDC redirect mismatch | Redirect URI in AA app matches YouTrack auth module exactly |
| **`invalid_scope`** | YouTrack **Scopes** = `openid profile email` (not `groups`); rebuild **`aa-web`**; AA app uses authorization code + RSA256 |
| **`oauth2-token-exchange-failed`** / `Unexpected character ('<'` | Alliance Auth OIDC app **Algorithm** must be **RSA with SHA-2 256 (`RS256`)** — empty algorithm causes a 500 HTML error at `/o/token/`. Fix in AA admin → OIDC application → **Algorithm** = RS256; or rebuild **`aa-web`** (auto-repairs on boot) |
| **`oauth2-token-exchange-failed`** / `No content to map` / YouTrack log `Response code from IdP: 308` | YouTrack auth module still has **`http://`** token/issuer URLs (Hub caches discovery). **Fix:** Administration → Access Management → Auth Modules → your OIDC module → set **all** endpoints to **`https://auth.<DOMAIN>/o/...`** (issuer, authorize, token, userinfo, JWKS). Re-save even if only the main URL looks correct. Rebuild **`aa-web`** if discovery still shows `http://`. Caddy also proxies **`http://auth.*`** directly so stale `http://` token URLs work after `docker compose up -d caddy` |
| “Access denied” after SSO | User has **Project Manager** group + `access_oidc` permission; OIDC app allows that group |
| Wizard/base URL wrong | YouTrack **Base URL** = `https://pm.<DOMAIN_NAME>` |
| OIDC key lost on rebuild | Set `AA_OIDC_RSA_PRIVATE_KEY` or persist `/app/site/oidc/` |

## OIDC endpoints (reference)

- Authorization: `https://auth.<DOMAIN>/o/authorize/`
- Token: `https://auth.<DOMAIN>/o/token/`
- Userinfo: `https://auth.<DOMAIN>/o/userinfo/`
- Issuer: `https://auth.<DOMAIN>/o/`

Claims include `name` (main character), `email`, and `groups` (Django groups + state) when `profile` scope is requested.
