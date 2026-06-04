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
            from corptools_corp_token import patch_corp_token_overrides

            patch_corp_token_overrides()
        except Exception:
            pass

        try:
            from structures_corp_token import patch_structures_fetch_token

            patch_structures_fetch_token()
        except Exception:
            pass

        try:
            from indy_hub_django_compat import patch_indy_hub_for_django5

            patch_indy_hub_for_django5()
        except Exception:
            pass

        try:
            from indy_hub_corp_token import patch_indy_hub_corp_tokens

            patch_indy_hub_corp_tokens()
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

        try:
            from oidc_provider import patch_oidc_urls

            patch_oidc_urls()
        except Exception:
            pass

        try:
            from corp_project_discord import ensure_corp_project_esi_scope_in_db

            ensure_corp_project_esi_scope_in_db()
        except Exception:
            pass

        # Ensure Celery registers industry_suite tasks (incl. daily digest) on worker boot.
        try:
            import industry_suite.tasks  # noqa: F401
        except Exception:
            pass

        self._register_charlink_import()

    @staticmethod
    def _register_charlink_import() -> None:
        """Ensure Charlink AppSettings row exists (industry_suite_corpprojectdiscord)."""
        try:
            from charlink.models import AppSettings

            AppSettings.objects.update_or_create(
                app_name="industry_suite_corpprojectdiscord",
                defaults={"default_selection": True},
            )
            AppSettings.objects.filter(
                app_name="industry_suite_corp_project_discord",
            ).delete()
        except Exception:
            pass
