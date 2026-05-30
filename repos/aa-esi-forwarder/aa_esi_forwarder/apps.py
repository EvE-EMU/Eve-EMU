import importlib

from django.apps import AppConfig
from django.urls import path


class AaEsiForwarderConfig(AppConfig):
    default_auto_field = "django.db.models.BigAutoField"
    name = "aa_esi_forwarder"
    label = "aa_esi_forwarder"
    verbose_name = "AA ESI Forwarder"

    def ready(self) -> None:
        from aa_esi_forwarder import views

        routes = [
            path(
                "internal/esi-forwarder/v1/health/",
                views.health_view,
                name="esi_forwarder_health",
            ),
            path(
                "internal/esi-forwarder/v1/token/",
                views.access_token_view,
                name="esi_forwarder_token",
            ),
            path(
                "internal/esi-forwarder/v1/proxy/<path:esi_path>",
                views.esi_proxy_view,
                name="esi_forwarder_proxy",
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
