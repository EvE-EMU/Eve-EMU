#!/usr/bin/env bash
# EvE-EMU unified Docker bootstrap (run from repository root).
set -euo pipefail
ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$ROOT"

if [ ! -f ".env" ]; then
  echo "Creating .env from .env.example"
  cp .env.example .env
fi

set -a
# shellcheck disable=SC1091
. ./.env
set +a

if ! python3 -c "import cryptography" 2>/dev/null; then
  echo "Installing cryptography on host for Fernet key generation (pip install --user cryptography) …"
  python3 -m pip install --user -q cryptography || {
    echo "Could not import/install cryptography; set CORE_TOKEN_ENCRYPTION_KEY manually in .env"
  }
fi

python3 deploy/patch_root_env.py

echo "Building images…"
docker compose build

echo "Starting stack…"
docker compose up -d db redis

echo "Waiting for Postgres…"
for i in $(seq 1 60); do
  if docker compose exec -T db pg_isready -U "${POSTGRES_USER:-eve}" -d "${POSTGRES_DB_CORE:-eve_emu_core}" >/dev/null 2>&1; then
    break
  fi
  sleep 1
  if [ "$i" -eq 60 ]; then
    echo "Postgres did not become ready in time." >&2
    exit 1
  fi
done

echo "Initializing FastAPI / SQLAlchemy schema (idempotent)…"
docker compose run --rm --no-deps core-api python scripts/docker_init_schema.py

echo "Running Django migrations (industry_suite)…"
docker compose run --rm --no-deps aa-web python manage.py migrate --noinput

echo "Starting remaining services…"
docker compose up -d

echo "Done. Core API: http://localhost:${CORE_API_PUBLISH_PORT:-8000}  Web: http://localhost:${CORE_WEB_PUBLISH_PORT:-3000}  AA (Alliance Auth): https://${DOMAIN_NAME:-eve-emu.com}/ (Caddy → aa-web; host ports ${CADDY_HTTP_PUBLISH_PORT:-80} / ${CADDY_HTTPS_PUBLISH_PORT:-443})"
