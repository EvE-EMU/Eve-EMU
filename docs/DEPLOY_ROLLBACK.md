# Deploy & rollback — `aa-web`/`aa-worker`/`aa-beat`

The procedure used for every `penguin_bridge`/`mfg_projects`/AA-extension
change tonight (2026-09-13), written down once so it doesn't have to be
re-derived under pressure at 3am by whoever's on call.

## Real gap this doc exists to flag

**There is currently only one tag per image** (`eve-emu-aa-web:latest`,
`eve-emu-aa-worker:latest`, `eve-emu-aa-beat:latest`) — a rebuild
*overwrites* the image that was actually serving traffic. There is
**no previous image to roll back to** once you've already rebuilt. Tag the
current image *before* building a new one if you want a real rollback path
(see below) — this wasn't done automatically tonight either; start doing it
going forward.

## Normal deploy

```bash
cd ~/eve-emu

# 1. Tag whatever is *currently running* as a rollback point, first.
for svc in aa-web aa-worker aa-beat; do
  docker tag "eve-emu-$svc:latest" "eve-emu-$svc:rollback"
done

# 2. Build the new image (all three share one Dockerfile/context - building
#    one warms the cache for the others; the final "exporting/unpacking"
#    step is slow — 15-20 min from a cold cache, seconds once warm — and
#    prints no progress for a few minutes even when it's working. Prefer
#    running this detached (`> build.log 2>&1 &`) over the CLI's own
#    backgrounding, which has OOM-killed the wrapper process (not the
#    actual build) more than once even with the host at <50% memory use.
docker compose build aa-web aa-worker aa-beat

# 3. Recreate the containers from the new image.
docker compose up -d aa-web aa-worker aa-beat

# 4. Wait for aa-web to actually report healthy (not just "Up") - a
#    healthcheck backed by 4 gunicorn workers each doing their own
#    AppConfig.ready() can take 1-3 minutes.
watch docker inspect --format '{{.State.Health.Status}}' eve-emu-aa-web-1

# 5. Check for import errors specifically - a broken import in a new
#    penguin_bridge/mfg_projects/etc. file won't fail the healthcheck by
#    itself if gunicorn's other workers are still up; it shows here first.
docker logs eve-emu-aa-web-1 2>&1 | grep -iE 'traceback|error|critical'

# 6. Verify the actual routes you changed respond (401 invalid_session is
#    correct for an unauthenticated check against a real /penguin/* route -
#    404 or 500 means something's actually wrong).
curl -s -o /dev/null -w 'HTTP %{http_code}\n' https://auth.eve-emu.com/penguin/health
curl -s https://auth.eve-emu.com/penguin/<the route you touched>
```

## Rolling back

```bash
cd ~/eve-emu
for svc in aa-web aa-worker aa-beat; do
  docker tag "eve-emu-$svc:rollback" "eve-emu-$svc:latest"
done
docker compose up -d --force-recreate aa-web aa-worker aa-beat
```

This only works if step 1 above was actually done before the bad build. If
it wasn't, the only way back is rebuilding from an earlier git commit:

```bash
git log --oneline -- deploy/aa_docker/          # find the commit before the bad change
git checkout <good-commit> -- deploy/aa_docker/
docker compose build aa-web aa-worker aa-beat
docker compose up -d aa-web aa-worker aa-beat
git checkout HEAD -- deploy/aa_docker/           # restore the working tree after
```

## New Django model / migration

Generate migrations for real — inside the container, against the real
models — rather than hand-writing them:

```bash
# 1. Edit the model file locally, then copy it into the *running* container
#    (this doesn't touch the image; it's a live hot-patch for generating
#    the migration only — the real fix still needs a rebuild per above).
docker cp deploy/aa_docker/<app>/models.py eve-emu-aa-web-1:/app/deploy/aa_docker/<app>/models.py

# 2. Generate the migration inside the container, where Django/the DB
#    connection actually exist.
docker exec -w /app/site eve-emu-aa-web-1 python3 manage.py makemigrations <app>

# 3. Pull the generated file back into the repo - do not hand-author it.
docker cp eve-emu-aa-web-1:/app/deploy/aa_docker/<app>/migrations/<new>.py \
  deploy/aa_docker/<app>/migrations/<new>.py

# 4. Apply it to the live DB now (safe — it's additive; the code using the
#    new field/model isn't live yet since it's only hot-patched, not
#    rebuilt).
docker exec -w /app/site eve-emu-aa-web-1 python3 manage.py migrate <app>

# 5. Commit the model + migration together, then do the normal deploy above.
```

## External reachability heartbeat

`scripts/uptime_check.sh` (added 2026-09-13, cron every 5 min) checks
`eve-emu.com`, `auth.eve-emu.com/penguin/health`, `wiki.eve-emu.com`, and
`wh.eve-emu.com` from outside Docker entirely — a container healthcheck only
knows the container itself is up, not that Caddy/DNS actually routes to it.
Added after a real incident the same day: a `docker compose up -d` aborted
partway through (see below) and left `caddy`/`aa-web`/`core-api`/etc. down
for several minutes with nothing paging anyone — it was only caught by a
manual check.

Logs every run to `backups/auto/uptime_check.log` regardless of config.
Posts to Discord only on a status *transition* (so a real outage doesn't
spam the channel every 5 minutes) if `INFRA_ALERTS_DISCORD_WEBHOOK_URL` is
set in `.env` — unset by default; pick whichever channel should get paged
and set it, see `.env.example`.

## `docker compose up -d` across the whole stack — the dependency-timeout trap

Recreating **every** service at once (e.g. after a `docker-compose.yml`
edit that touches all of them, like the logging-rotation change) can abort
partway through: if `db` needs to run WAL recovery from an unclean prior
shutdown, it can take 1-2+ minutes to report healthy, and compose's
dependency wait has a timeout shorter than that. When it times out, compose
does **not** retry — it stops, leaving every service that `depends_on: db`
(which is most of them, including `caddy`) sitting in `Created` state,
i.e. stopped. This actually happened 2026-09-13.

The fix is simply to run `docker compose up -d` again once `db` is healthy
(`docker inspect eve-emu-db-1 --format '{{.State.Health.Status}}'`) — compose
picks up where it left off and starts everything still in `Created`. Always
re-check `docker compose ps` (not just the command's own exit output) after
a whole-stack `up -d` to make sure nothing was left behind.

## Database backup, before anything risky

`scripts/backup_databases.sh` (added 2026-09-13, nightly at 03:00 via cron)
dumps all 4 live Postgres databases, mediawiki's MariaDB, and both MySQL
`emums` databases straight from their running containers — no password
needed in the script itself, each dump runs as the container's own
already-authenticated tooling. Run it manually before anything you're
genuinely unsure about:

```bash
./scripts/backup_databases.sh
```

Restoring a specific one:

```bash
docker cp backups/auto/<timestamp>/eve_emu_aa.dump eve-emu-db-1:/tmp/restore.dump
docker exec eve-emu-db-1 pg_restore -U eve -d eve_emu_aa --clean --if-exists /tmp/restore.dump
docker exec eve-emu-db-1 rm /tmp/restore.dump
```
