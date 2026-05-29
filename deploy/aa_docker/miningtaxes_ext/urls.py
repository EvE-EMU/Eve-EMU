from django.urls import path

from . import views

app_name = "miningtaxes_ext"

urlpatterns = [
    path("moon-ore-report/", views.moon_ore_report_page, name="moon_ore_report"),
    path("moon-ore-report.json", views.moon_ore_report_json, name="moon_ore_report_json"),
    path("moon-ore-report.csv", views.moon_ore_report_csv, name="moon_ore_report_csv"),
    path(
        "user/<int:user_pk>/ore-totals.json",
        views.user_ore_totals_json,
        name="user_ore_totals_json",
    ),
    path(
        "user/<int:user_pk>/ledger-ore.json",
        views.user_ledger_ore_json,
        name="user_ledger_ore_json",
    ),
]
