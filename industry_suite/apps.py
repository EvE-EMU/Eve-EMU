from django.apps import AppConfig


class IndustrySuiteConfig(AppConfig):
    default_auto_field = "django.db.models.BigAutoField"
    name = "industry_suite"
    verbose_name = "EvE-EMU Industrial Command"

    def ready(self) -> None:
        # Alliance Auth v5.0.1 + Django 5.2: admin calls str(obj) on AnalyticsIdentifier;
        # upstream __str__ returns a lazy gettext proxy → TypeError in admin change view.
        try:
            from allianceauth.analytics.models import AnalyticsIdentifier
            from django.utils.translation import gettext_lazy as _lazy

            def _analytics_identifier_str(self) -> str:
                return str(_lazy("Analytics Identifier"))

            AnalyticsIdentifier.__str__ = _analytics_identifier_str  # type: ignore[method-assign]
        except Exception:
            pass

        try:
            from corptools_postgres_compat import patch_corptools_for_postgresql

            patch_corptools_for_postgresql()
        except Exception:
            pass

        try:
            from indy_hub_postgres_compat import patch_indy_hub_for_postgresql

            patch_indy_hub_for_postgresql()
        except Exception:
            pass

        try:
            from top_postgres_compat import ensure_top_static_dir, patch_top_for_postgresql

            ensure_top_static_dir()
            patch_top_for_postgresql()
        except Exception:
            pass

        try:
            from metenox_compat import patch_metenox_for_runtime

            patch_metenox_for_runtime()
        except Exception:
            pass
