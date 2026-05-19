from django.apps import AppConfig


class CorpOrdersConfig(AppConfig):
    default_auto_field = "django.db.models.BigAutoField"
    name = "corp_orders"
    verbose_name = "Corp stock orders"

    def ready(self) -> None:
        from corp_orders import signals  # noqa: F401
