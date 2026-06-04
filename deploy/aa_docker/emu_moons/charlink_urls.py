"""Charlink audit URL aliases (AppSettings name != Charlink app label)."""

from django.urls import path
from django.views.generic import RedirectView

app_name = "emu_moons_charlink"

urlpatterns = [
    path(
        "",
        RedirectView.as_view(
            url="/charlink/audit/app/emu_moons/",
            permanent=False,
        ),
        name="charlink_audit_alias",
    ),
]
