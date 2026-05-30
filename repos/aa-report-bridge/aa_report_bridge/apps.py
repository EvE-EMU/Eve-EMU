import importlib
import logging

from django.apps import AppConfig
from django.urls import path

logger = logging.getLogger(__name__)


class AaReportBridgeConfig(AppConfig):
    default_auto_field = "django.db.models.BigAutoField"
    name = "aa_report_bridge"
    label = "aa_report_bridge"
    verbose_name = "AA Report Bridge"

    def ready(self) -> None:
        from aa_report_bridge import views
        from aa_report_bridge.signals import connect_watchers

        routes = [
            path(
                "internal/report-bridge/v1/health/",
                views.health_view,
                name="report_bridge_health",
            ),
            path(
                "internal/report-bridge/v1/resources/",
                views.resources_view,
                name="report_bridge_resources",
            ),
            path(
                "internal/report-bridge/v1/export/<str:resource>/",
                views.export_view,
                name="report_bridge_export",
            ),
            path(
                "internal/report-bridge/v1/webhooks/test/",
                views.webhook_test_view,
                name="report_bridge_webhook_test",
            ),
        ]
        names = {r.name for r in routes}
        for mod_name in ("eve_auth.urls", "allianceauth.urls", "myauth.urls", "urls"):
            try:
                root = importlib.import_module(mod_name)
            except ImportError:
                continue
            patterns = getattr(root, "urlpatterns", None)
            if patterns is None:
                continue
            existing = {getattr(p, "name", None) for p in patterns}
            for route in routes:
                if route.name not in existing:
                    patterns.insert(0, route)
            if names <= existing | names:
                break

        try:
            connect_watchers()
        except Exception:  # noqa: BLE001
            logger.exception("report_bridge: failed to connect signal watchers")
