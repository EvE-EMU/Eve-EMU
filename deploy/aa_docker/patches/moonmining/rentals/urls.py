"""URL routes for renter management UI and JSON API."""

from django.urls import path

from . import api_views, views

urlpatterns = [
    path("renters/", views.renter_management, name="renter_management"),
    path("renters/settings/", views.save_settings, name="renter_settings"),
    path("renters/moon/<int:moon_id>/", views.configure_lease, name="configure_lease"),
    path("renters/lease/<int:lease_id>/evict/", views.evict_lease, name="evict_lease"),
    path(
        "renters/application/<int:application_id>/approve/",
        views.approve_application_view,
        name="approve_application",
    ),
    path(
        "renters/application/<int:application_id>/reject/",
        views.reject_application_view,
        name="reject_application",
    ),
    path("api/rentals/leases", api_views.api_leases, name="api_leases"),
    path("api/rentals/config", api_views.api_config, name="api_config"),
    path(
        "api/rentals/leases/<int:lease_id>/evict",
        api_views.api_lease_evict,
        name="api_lease_evict",
    ),
    path("api/rentals/users", api_views.api_user_search, name="api_user_search"),
]
