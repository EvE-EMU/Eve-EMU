from django.apps import AppConfig


class MoonTsarConfig(AppConfig):
    default_auto_field = "django.db.models.BigAutoField"
    name = "moon_tsar"
    verbose_name = "Moon Tsar"

    def ready(self) -> None:
        import moon_tsar.auth_hooks  # noqa: F401
