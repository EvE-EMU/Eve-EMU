FROM python:3.12-slim

ENV PYTHONDONTWRITEBYTECODE=1 PYTHONUNBUFFERED=1

# mysqlclient (Alliance Auth dependency) needs MariaDB client headers; PostgreSQL via psycopg2-binary wheels.
RUN apt-get update \
    && apt-get install -y --no-install-recommends \
        libpq5 \
        gcc g++ pkg-config git \
        libmariadb-dev-compat libmariadb-dev \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

RUN pip install --no-cache-dir "pip==26.1.1"

COPY allianceauth /opt/allianceauth
COPY deploy/aa_docker/requirements-aa-extension-deps.txt /tmp/requirements-aa-extension-deps.txt
COPY deploy/aa_docker/requirements-aa-extension-apps.txt /tmp/requirements-aa-extension-apps.txt
RUN pip install --no-cache-dir -e /opt/allianceauth \
    -r /tmp/requirements-aa-extension-deps.txt \
    gunicorn whitenoise "psycopg2-binary>=2.9,<3" \
    && pip install --no-cache-dir -r /tmp/requirements-aa-extension-apps.txt --no-deps \
    && pip install --no-cache-dir "pip==26.1.1"

COPY deploy/aa_docker/patches/indy_hub/ /usr/local/lib/python3.12/site-packages/indy_hub/migrations/

COPY industry_suite /app/industry_suite
COPY buyback_v2 /app/buyback_v2
COPY corp_orders /app/corp_orders
COPY standing_fleet_tracker /app/standing_fleet_tracker
COPY sde_wiki /app/sde_wiki

WORKDIR /app/site
RUN python -m allianceauth.bin.allianceauth start eve_auth . \
    && python -m allianceauth.bin.allianceauth update eve_auth

COPY deploy/aa_docker/eve_auth/celery.py /app/site/eve_auth/celery.py
COPY deploy/aa_docker/local.py /app/site/eve_auth/settings/local.py
COPY deploy/aa_docker/esi_clients_compat.py /app/deploy/aa_docker/esi_clients_compat.py
COPY deploy/aa_docker/metenox_compat.py /app/deploy/aa_docker/metenox_compat.py
# Community apps still on ``esi.clients`` imports — swap to OpenAPI provider (django-esi 9).
COPY deploy/aa_docker/patches/esi_openapi_providers/killtracker/providers.py /usr/local/lib/python3.12/site-packages/killtracker/providers.py
COPY deploy/aa_docker/patches/esi_openapi_providers/standingssync/providers.py /usr/local/lib/python3.12/site-packages/standingssync/providers.py
COPY deploy/aa_docker/patches/esi_openapi_providers/moonmining/providers.py /usr/local/lib/python3.12/site-packages/moonmining/providers.py
COPY deploy/aa_docker/patches/esi_openapi_providers/buybackprogram/providers.py /usr/local/lib/python3.12/site-packages/buybackprogram/providers.py
COPY deploy/aa_docker/patches/esi_openapi_providers/structures/providers.py /usr/local/lib/python3.12/site-packages/structures/providers.py
COPY deploy/aa_docker/corptools_postgres_compat.py /app/deploy/aa_docker/corptools_postgres_compat.py
COPY deploy/aa_docker/indy_hub_postgres_compat.py /app/deploy/aa_docker/indy_hub_postgres_compat.py
COPY deploy/aa_docker/top_postgres_compat.py /app/deploy/aa_docker/top_postgres_compat.py
# Django 5 upsert: bulk_create(update_conflicts=True) requires unique_fields (aa-sov-timer 4.1.0).
COPY deploy/aa_docker/patches/sovtimer/tasks.py /usr/local/lib/python3.12/site-packages/sovtimer/tasks.py
# aa-ledger 3.0.0 charlink hook still referenced renamed ORM fields (corporation / character).
COPY deploy/aa_docker/patches/ledger/thirdparty/charlink_hook.py /usr/local/lib/python3.12/site-packages/ledger/thirdparty/charlink_hook.py
COPY deploy/aa_docker/patches/ledger/auth_hooks.py /usr/local/lib/python3.12/site-packages/ledger/auth_hooks.py
# aa-metenox 1.6.3: SDE gap + DataTables GET edge cases → 500 on /metenox/moons.
COPY deploy/aa_docker/patches/metenox/views/moons.py /usr/local/lib/python3.12/site-packages/metenox/views/moons.py
# aa-market-manager 2.0.0: eve_sde ItemType uses group/market_group/parent_group, not item_* names.
COPY deploy/aa_docker/patches/marketmanager/models.py /usr/local/lib/python3.12/site-packages/marketmanager/models.py
COPY deploy/aa_docker/patches/marketmanager/admin.py /usr/local/lib/python3.12/site-packages/marketmanager/admin.py
COPY deploy/aa_docker/patches/marketmanager/tasks.py /usr/local/lib/python3.12/site-packages/marketmanager/tasks.py
COPY deploy/aa_docker/patches/marketmanager/cogs/marketmanager.py /usr/local/lib/python3.12/site-packages/marketmanager/cogs/marketmanager.py
COPY deploy/aa_docker/patches/marketmanager/marketbrowser-bs5.html /usr/local/lib/python3.12/site-packages/marketmanager/templates/marketmanager/marketbrowser-bs5.html
COPY deploy/aa_docker/patches/marketmanager/item_details-bs5.html /usr/local/lib/python3.12/site-packages/marketmanager/templates/marketmanager/marketbrowser/item_details-bs5.html
# aa-taskmonitor: kill single queued Celery task from Django admin
# Alliance Auth Discord: allow Django boot when DISCORD_BOT_TOKEN is unset (aadiscordbot import).
COPY deploy/aa_docker/patches/discord/core.py /opt/allianceauth/allianceauth/services/modules/discord/core.py
COPY deploy/aa_docker/patches/taskmonitor/views.py /usr/local/lib/python3.12/site-packages/taskmonitor/views.py
COPY deploy/aa_docker/patches/taskmonitor/urls.py /usr/local/lib/python3.12/site-packages/taskmonitor/urls.py
COPY deploy/aa_docker/taskmonitor_patch.py /app/deploy/aa_docker/taskmonitor_patch.py
COPY deploy/aa_docker/repair_indy_hub_migrations.py /app/deploy/aa_docker/repair_indy_hub_migrations.py
COPY deploy/aa_docker/extensions /app/deploy/aa_docker/extensions
COPY deploy/aa_docker/market_bridge /app/deploy/aa_docker/market_bridge
COPY deploy/aa_docker/esi_compat_app /app/deploy/aa_docker/esi_compat_app
COPY deploy/aa_docker/templates /app/deploy/aa_docker/templates
COPY deploy/aa_docker/static /app/deploy/aa_docker/static

ENV PYTHONPATH=/app/deploy/aa_docker:/app:/app/site

RUN mkdir -p log

COPY docker/django-aa/entrypoint.py /docker-entrypoint.py
RUN chmod +x /docker-entrypoint.py

WORKDIR /app/site
EXPOSE 8080

ENTRYPOINT ["python3", "/docker-entrypoint.py"]
CMD ["celery", "-A", "eve_auth", "worker", "-l", "INFO"]
