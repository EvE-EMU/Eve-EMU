from django.apps import AppConfig


class EmuMoonsConfig(AppConfig):
    default_auto_field = "django.db.models.BigAutoField"
    name = "emu_moons"
    verbose_name = "EMU Moons"

    @staticmethod
    def _register_charlink_import() -> None:
        """Ensure Charlink AppSettings row exists (emu_moons_corpminingobserver)."""
        try:
            from charlink.models import AppSettings

            AppSettings.objects.get_or_create(
                app_name="emu_moons_corpminingobserver",
                defaults={"default_selection": True},
            )
        except Exception:
            pass

    def ready(self) -> None:
        from emu_moons.observer_scopes import ensure_emu_moons_observer_scopes_in_db

        ensure_emu_moons_observer_scopes_in_db()
        import emu_moons.auth_hooks  # noqa: F401
        import emu_moons.signals  # noqa: F401
        self._register_charlink_import()
