from django.urls import path

from . import views

app_name = "emu_moons"

urlpatterns = [
    path("", views.index, name="index"),
    path("invoices/", views.invoice_list, name="invoice_list"),
    path("account/", views.account_statement, name="account_statement"),
    path("account/<str:username>/", views.account_statement, name="account_statement_user"),
    path("invoices/<str:invoice_number>/", views.invoice_detail, name="invoice_detail"),
    path("naughty/", views.naughty_list, name="naughty_list"),
    path("alliance/", views.alliance_dashboard, name="alliance_dashboard"),
    path("corp/", views.corp_dashboard, name="corp_dashboard"),
    path("admin/settings/", views.admin_settings, name="admin_settings"),
]
