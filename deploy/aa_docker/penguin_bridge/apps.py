from __future__ import annotations

import logging

from django.apps import AppConfig

logger = logging.getLogger("penguin_bridge")


class PenguinBridgeConfig(AppConfig):
    default_auto_field = "django.db.models.BigAutoField"
    name = "penguin_bridge"
    label = "penguin_bridge"
    verbose_name = "EVE-Penguin bridge"

    def ready(self) -> None:
        from django.urls import path, re_path

        import eve_auth.urls as root_urls

        from penguin_bridge.fittings import fittings
        from penguin_bridge.industry import freight_quote, freight_systems, structures
        from penguin_bridge.jobs import job_detail, jobs
        from penguin_bridge.pings import pings
        from penguin_bridge.projects import project_detail, projects
        from penguin_bridge.wh import wh
        from penguin_bridge.views import (
            authorize,
            esi_char,
            esi_corp,
            health,
            logout,
            me,
        )

        routes = [
            path("penguin/authorize", authorize, name="penguin_authorize"),
            path("penguin/me", me, name="penguin_me"),
            path("penguin/logout", logout, name="penguin_logout"),
            path("penguin/health", health, name="penguin_health"),
            path("penguin/fittings", fittings, name="penguin_fittings"),
            path("penguin/wh", wh, name="penguin_wh"),
            path("penguin/pings", pings, name="penguin_pings"),
            path("penguin/structures", structures, name="penguin_structures"),
            path("penguin/freight/systems", freight_systems, name="penguin_freight_systems"),
            path("penguin/freight/quote", freight_quote, name="penguin_freight_quote"),
            path("penguin/projects", projects, name="penguin_projects"),
            path(
                "penguin/projects/<str:project_ref>",
                project_detail,
                name="penguin_project_detail",
            ),
            path("penguin/jobs", jobs, name="penguin_jobs"),
            path("penguin/jobs/<int:job_id>", job_detail, name="penguin_job_detail"),
            re_path(
                r"^penguin/esi/corp/(?P<corporation_id>\d+)/(?P<esi_path>.+)$",
                esi_corp,
                name="penguin_esi_corp",
            ),
            re_path(
                r"^penguin/esi/(?P<character_id>\d+)/(?P<esi_path>.+)$",
                esi_char,
                name="penguin_esi_char",
            ),
        ]

        existing = {getattr(p, "name", None) for p in root_urls.urlpatterns}
        added = 0
        for route in routes:
            if route.name not in existing:
                root_urls.urlpatterns.insert(0, route)
                added += 1
        logger.info("penguin_bridge: mounted %d /penguin/* routes", added)

        try:
            from admin_urls_refresh import refresh_admin_site_urls

            refresh_admin_site_urls()
        except Exception:
            logger.debug("penguin_bridge: admin URL refresh skipped", exc_info=True)
