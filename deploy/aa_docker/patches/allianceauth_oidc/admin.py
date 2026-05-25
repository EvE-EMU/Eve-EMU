from django.contrib import admin
from django.contrib.auth import get_user_model

has_email = hasattr(get_user_model(), "email")


class ApplicationAdmin(admin.ModelAdmin):
    list_display = (
        "id",
        "name",
        "user",
        "client_type",
        "authorization_grant_type",
        "algorithm",
    )
    list_filter = (
        "client_type",
        "authorization_grant_type",
        "algorithm",
        "skip_authorization",
    )
    filter_horizontal = ("states", "groups")
    radio_fields = {
        "client_type": admin.HORIZONTAL,
        "authorization_grant_type": admin.VERTICAL,
        "algorithm": admin.VERTICAL,
    }
    search_fields = ("name",) + (("user__email",) if has_email else ())
    raw_id_fields = ("user",)
