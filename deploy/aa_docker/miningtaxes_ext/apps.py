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

        try:
            from miningtaxes_structure_exclusions import (
                apply_miningtaxes_structure_exclusion_patch,
            )

            apply_miningtaxes_structure_exclusion_patch()
        except Exception:
            pass

        try:
            from miningtaxes_summary_perf import apply_miningtaxes_summary_perf_patch

            apply_miningtaxes_summary_perf_patch()
        except Exception:
            pass

        try:
            from miningtaxes_negative_balance_patch import (
                apply_miningtaxes_negative_balance_patch,
            )

            apply_miningtaxes_negative_balance_patch()
        except Exception:
            pass

        try:
            from miningtaxes_ore_tax_rates_patch import (
                apply_miningtaxes_ore_tax_rates_patch,
            )

            apply_miningtaxes_ore_tax_rates_patch()
        except Exception:
            pass

        try:
            from miningtaxes_unauth_miner_alert import (
                apply_miningtaxes_unauth_miner_alert_patch,
            )

            apply_miningtaxes_unauth_miner_alert_patch()
        except Exception:
            pass
