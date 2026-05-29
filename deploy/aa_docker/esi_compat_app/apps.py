from django.apps import AppConfig


class EsiCompatConfig(AppConfig):
    default_auto_field = "django.db.models.BigAutoField"
    name = "esi_compat_app"
    label = "esi_compat_app"

    def ready(self) -> None:
        from esi_clients_compat import _patch_esitag_legacy_operation_names

        _patch_esitag_legacy_operation_names()

        try:
            from buybackprogram_esi_compat import patch_buybackprogram_esi

            patch_buybackprogram_esi()
        except Exception:
            pass

        try:
            from taskmonitor_patch import patch_taskmonitor_kill_queued_task

            patch_taskmonitor_kill_queued_task()
        except Exception:
            pass
