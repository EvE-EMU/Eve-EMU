"""Routes for Mail Relay."""

from django.urls import path

from . import views

app_name = "mailrelay"

urlpatterns = [
    path(
        "admin_update_discord_channels",
        views.admin_update_discord_channels,
        name="admin_update_discord_channels",
    ),
]
