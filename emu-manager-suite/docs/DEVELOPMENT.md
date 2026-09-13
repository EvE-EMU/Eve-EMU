# EMU Manager Suite — Development

## Local backend (without Docker)

```bash
cd emu-manager-suite/backend
python3 -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt

# Start MySQL locally or point at docker emums-mysql on localhost:3306
export EMUMS_DATABASE_URL='mysql+aiomysql://emums:emums@127.0.0.1:3306/emums?charset=utf8mb4'
export EMUMS_API_KEY=emums-dev-key-change-me
export EMUMS_SEED_DEMO_DATA=1

uvicorn app.main:app --reload --port 8020
```

## Local frontend

```bash
cd emu-manager-suite/frontend
npm install
export EMUMS_API_URL=http://127.0.0.1:8020/v1
export EMUMS_API_KEY=emums-dev-key-change-me
npm run dev
```

Open http://localhost:3020

## Adding an API endpoint

1. Define Pydantic schema in `app/schemas/__init__.py`
2. Add route module under `app/api/v1/`
3. Register in `app/api/v1/router.py`
4. Update `docs/API.md`
5. Add server fetch in `frontend/src/lib/api.ts`
6. Build UI page or extend existing page

## Adding a UI page

1. Create `frontend/src/app/<route>/page.tsx`
2. Use server component + `fetchX()` from `lib/api.ts`
3. Add nav item in `AppShell.tsx`
4. Reuse `Panel`, `PropagandaBanner`, chart components

## Database migrations (future)

Currently uses `Base.metadata.create_all` on startup for speed. When schema stabilizes:

```bash
alembic init alembic
# configure sqlalchemy.url from EMUMS_DATABASE_URL
alembic revision --autogenerate -m "description"
alembic upgrade head
```

Document migration in PR when switching from create_all.

## Visual-first iteration

Demo data is seeded when `OrgSettings` is empty. To reset:

```bash
docker compose exec emums-mysql mysql -uemums -pemums emums -e "DROP DATABASE emums; CREATE DATABASE emums;"
docker compose restart emums-api
```

## Agent continuation

When resuming work in Cursor:

1. Read `emu-manager-suite/README.md` and `docs/ARCHITECTURE.md`
2. Check OpenAPI at `/docs` for current surface
3. Domain reference: `deploy/aa_docker/emu_moons/` (Django original)
4. Do not wire EMUMS to Alliance Auth without explicit request
