# Security policy — EvE-EMU

## Reporting a vulnerability

Please report sensitive issues **privately** (for example GitHub Security Advisories for this repository, or maintainer DM/email if published). Do not post working exploits, dumps of tokens, or live webhook URLs in public issues.

## Priority topics for this project

### ESI refresh tokens and access tokens

- **At rest:** `core/` stores refresh material encrypted (Fernet + `CORE_TOKEN_ENCRYPTION_KEY`). Protect that key like a production secret; rotation invalidates existing ciphertext—plan migrations or forced re-link.
- **In transit:** use HTTPS everywhere between users, reverse proxies, `core/`, and AA.
- **In logs:** never log `Authorization` headers, OAuth codes, refresh tokens, or decrypted payloads. Redact query strings that contain OAuth `code` or `state` if you capture HTTP logs.
- **Scopes:** request the **minimum** ESI scopes required for each feature; document scopes in your operator runbook (see also **ESI Scoping** in `PRIVACY.md`).

### Discord webhooks

- **Treat URLs as secrets.** A leaked webhook URL allows arbitrary message injection into your server until you rotate the webhook in Discord.
- **Sanitize outbound content** before POSTing to webhooks (strip control characters, cap length, avoid `@everyone` unless explicitly intended and allowed by your mention policy).
- **Validate inbound** webhook-like HTTP callbacks (shared secrets, timing-safe comparison, replay protection) if you add HTTP receivers for zKill or other feeds—never trust unauthenticated payloads.

### Discord bot token

- The bot token grants full bot identity. Keep `.env` out of git (see `.gitignore`); rotate immediately if leaked.

### Character audits (HR)

- Audits must comply with the **EVE Developer License Agreement** and CCP guidance on personal data. Use ESI data only for the stated org purpose, retain only what you need, restrict access to authorized staff, and document your corp/alliance policy (see **Corp-Level Data Audits** in `PRIVACY.md` / `TERMS.md` placeholders).

## Supported versions

Security fixes are applied to the **default branch** of this repository. Self-hosted deployments should track that branch or tagged releases when available.
