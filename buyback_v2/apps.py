from django.apps import AppConfig


class BuybackV2Config(AppConfig):
    default_auto_field = "django.db.models.BigAutoField"
    name = "buyback_v2"
    verbose_name = "Buyback v2 (Janice pricing)"

    def ready(self) -> None:
        import buyback_v2.auth_hooks  # noqa: F401
        import buyback_v2.signals  # noqa: F401

        from buyback_v2.hooks import install_buyback_v2_hooks

        install_buyback_v2_hooks()
