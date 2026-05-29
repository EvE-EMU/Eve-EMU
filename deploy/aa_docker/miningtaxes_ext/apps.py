from django.apps import AppConfig


class MiningtaxesExtConfig(AppConfig):
    default_auto_field = "django.db.models.BigAutoField"
    name = "miningtaxes_ext"
    verbose_name = "Mining Taxes (EvE-EMU)"

    def ready(self) -> None:
        import miningtaxes_ext.auth_hooks  # noqa: F401

        try:
            from miningtaxes_notify_patch import apply_miningtaxes_notify_patch

            apply_miningtaxes_notify_patch()
        except Exception:
            pass
