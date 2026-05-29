"""Django AppConfig for eve-emu extension hooks (runs after apps are ready)."""

from django.apps import AppConfig


class EveEmuHooksConfig(AppConfig):
    default_auto_field = "django.db.models.BigAutoField"
    name = "extensions.hooks_apps"
    label = "eve_emu_hooks"
    verbose_name = "Eve EMU hooks"

    def ready(self) -> None:
        from extensions.character_affiliation_patch import (
            patch_eve_character_update_from_affiliation,
        )
        from extensions.discord_group_sync import (
            ensure_discord_service_state_permissions,
            register_discord_group_nickname_sync,
        )

        patch_eve_character_update_from_affiliation()
        register_discord_group_nickname_sync()
        ensure_discord_service_state_permissions()
