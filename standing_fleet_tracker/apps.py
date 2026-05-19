from django.apps import AppConfig


class StandingFleetTrackerConfig(AppConfig):
    default_auto_field = "django.db.models.BigAutoField"
    name = "standing_fleet_tracker"
    verbose_name = "Standing Fleet Tracker"

    def ready(self) -> None:
        from standing_fleet_tracker import auth_hooks  # noqa: F401
