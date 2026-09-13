#!/usr/bin/env bash
# External reachability check for the public endpoints — run on a cron,
# independent of Docker healthchecks (which only know a container is up,
# not that Caddy/DNS/the network path in front of it actually works).
#
# Added 2026-09-13 after a real incident: `docker compose up -d` aborted
# partway through (a dependency healthcheck timeout) and left caddy/aa-web/
# core-api/etc. stopped for several minutes with nothing paging anyone —
# it was only caught by a manual check. This is the "even a lightweight ...
# Discord-bot heartbeat" item from the platform improvement plan.
#
# State-based: only posts to Discord on a status *transition* (up->down or
# down->up), not on every failing run, so a real outage doesn't spam the
# channel every 5 minutes. Always logs every run locally regardless of
# whether Discord posting is configured.
#
# Usage: ./scripts/uptime_check.sh   (intended for cron; see crontab -l)
#
# Optional: set INFRA_ALERTS_DISCORD_WEBHOOK_URL in .env to also post
# transitions to Discord. Unset = local logging only, no network call.
set -euo pipefail
cd "$(dirname "${BASH_SOURCE[0]}")/.."

LOG_DIR="backups/auto"
LOG_FILE="$LOG_DIR/uptime_check.log"
STATE_FILE="$LOG_DIR/.uptime_state"
mkdir -p "$LOG_DIR"
touch "$STATE_FILE"

WEBHOOK_URL=""
if [ -f .env ]; then
  WEBHOOK_URL="$(grep -E '^INFRA_ALERTS_DISCORD_WEBHOOK_URL=' .env | head -1 | cut -d= -f2- || true)"
fi

# name|url|expected_http_code
CHECKS=(
  "eve-emu.com|https://eve-emu.com/|200"
  "auth.eve-emu.com|https://auth.eve-emu.com/penguin/health|200"
  "wiki.eve-emu.com|https://wiki.eve-emu.com/|301"
  "wh.eve-emu.com|https://wh.eve-emu.com/|302"
)

now="$(date -u +'%Y-%m-%dT%H:%M:%SZ')"
notify() {
  local msg="$1"
  echo "$now $msg" >>"$LOG_FILE"
  if [ -n "$WEBHOOK_URL" ]; then
    curl -s -m 10 -H "Content-Type: application/json" \
      -d "{\"content\": $(printf '%s' "$msg" | python3 -c 'import json,sys; print(json.dumps(sys.stdin.read()))')}" \
      "$WEBHOOK_URL" >/dev/null || echo "$now WARN: failed to post to Discord webhook" >>"$LOG_FILE"
  fi
}

for entry in "${CHECKS[@]}"; do
  IFS='|' read -r name url expected <<<"$entry"
  code="$(curl -s -o /dev/null -m 15 -w '%{http_code}' "$url" || echo "000")"
  prev="$(grep -E "^${name}=" "$STATE_FILE" 2>/dev/null | cut -d= -f2- || echo "unknown")"

  if [ "$code" = "$expected" ]; then
    cur="up"
  else
    cur="down"
  fi

  echo "$now $name -> HTTP $code (expected $expected) [$cur]" >>"$LOG_FILE"

  if [ "$cur" != "$prev" ]; then
    if [ "$cur" = "down" ]; then
      notify "🔴 **$name** is DOWN — got HTTP $code, expected $expected ($url)"
    elif [ "$prev" != "unknown" ]; then
      notify "🟢 **$name** recovered — HTTP $code ($url)"
    fi
    # Update state (preserve other entries)
    grep -vE "^${name}=" "$STATE_FILE" >"$STATE_FILE.tmp" 2>/dev/null || true
    mv "$STATE_FILE.tmp" "$STATE_FILE"
    echo "${name}=${cur}" >>"$STATE_FILE"
  fi
done
