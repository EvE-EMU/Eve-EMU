from django.apps import AppConfig


class MoonRentalsConfig(AppConfig):
    default_auto_field = "django.db.models.BigAutoField"
    name = "moon_rentals"
    verbose_name = "Moon rentals"

    def ready(self) -> None:
        import moon_rentals.auth_hooks  # noqa: F401
