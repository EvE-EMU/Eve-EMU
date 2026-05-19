from django.urls import path

from buyback_v2 import views

app_name = "buyback_v2"

urlpatterns = [
    path("", views.public_index, name="public_index"),
    path("program/<int:program_pk>/", views.public_program_calculate, name="public_calculate"),
    path("program/<int:program_pk>/tier/", views.tier_preview, name="tier_preview"),
]
