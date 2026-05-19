from django.contrib import admin

from .models import IdlerHandler, MumbleServerServer, MumbleUser
from ...admin import ServicesUserAdmin

@admin.register(MumbleUser)
class MumbleUserAdmin(ServicesUserAdmin):
    list_display = ServicesUserAdmin.list_display + (
        'username',
        'release',
        'version'
    )
    search_fields = ServicesUserAdmin.search_fields + (
        'username',
    )


@admin.register(MumbleServerServer)
class MumbleServerServerAdmin(admin.ModelAdmin):
    list_display = ["name", "ip", "port", "slice", "virtual_servers", "avatar_enable", "reject_on_error", "offset"]
    list_filter = ["slice", "avatar_enable", "reject_on_error", "offset"]
    search_fields = ["name"]


@admin.register(IdlerHandler)
class IdlerhandlerAdmin(admin.ModelAdmin):
    list_display = ["name", "enabled", "seconds", "interval", "channel", "denylist"]
    list_filter = ["enabled", "denylist"]
    search_fields = ["name"]
