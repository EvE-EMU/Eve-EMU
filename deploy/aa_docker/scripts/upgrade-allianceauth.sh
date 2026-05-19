#!/usr/bin/env sh
# Upgrade Alliance Auth submodule + rebuild aa-* images (default tag: v5.0.1).
set -eu

TAG="${AA_UPGRADE_TAG:-v5.0.1}"
ROOT="$(cd "$(dirname "$0")/../../.." && pwd)"

cd "$ROOT"
git submodule update --init allianceauth
(
  cd allianceauth
  git fetch --tags origin
  git checkout "$TAG"
)

echo "allianceauth submodule: $(cd allianceauth && git describe --tags --always)"

docker compose build aa-web aa-worker aa-beat aa-discordbot
docker compose up -d aa-web aa-worker aa-beat aa-discordbot

docker compose exec aa-web python manage.py check
docker compose exec aa-web python manage.py sync_sde_compat || true
docker compose exec aa-web python manage.py packagemonitorcli refresh || true

echo "Done. Alliance Auth upgrade to $TAG complete."
