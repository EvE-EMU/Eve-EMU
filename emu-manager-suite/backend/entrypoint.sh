#!/bin/sh
set -e

echo "EMUMS: running Alembic migrations..."
python -m app.db.migrate

exec "$@"
