from django.urls import path

from moon_tsar import views

app_name = "moon_tsar"

urlpatterns = [
    path("", views.dashboard, name="dashboard"),
    path("settings/", views.settings_view, name="settings"),
    path("settings/tax-rates/", views.tax_rates_save, name="tax_rates_save"),
    path("bills/", views.bill_list, name="bill_list"),
    path("bill/<uuid:public_id>/", views.bill_detail, name="bill_detail"),
    path("renter/", views.renter_portal, name="renter_portal"),
    path("heatmap/", views.heatmap, name="heatmap"),
]
