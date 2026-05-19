"""
URL config
"""

# Django
from django.urls import include, path

# AA Fleet Finder
from fleetfinder import views

app_name: str = "fleetfinder"  # pylint: disable=invalid-name

urlpatterns = [
    path(route="", view=views.dashboard, name="dashboard"),
    path(route="fleet/create/", view=views.create_fleet, name="create_fleet"),
    path(route="fleet/save/", view=views.save_fleet, name="save_fleet"),
    path(route="fleet/<int:fleet_id>/join/", view=views.join_fleet, name="join_fleet"),
    path(
        route="fleet/<int:fleet_id>/details/",
        view=views.fleet_details,
        name="fleet_details",
    ),
    path(route="fleet/<int:fleet_id>/edit/", view=views.edit_fleet, name="edit_fleet"),
    # Ajax calls
    path(
        route="ajax/",
        view=include(
            [
                path(
                    route="dashboard/", view=views.ajax_dashboard, name="ajax_dashboard"
                ),
                path(
                    route="fleet/<int:fleet_id>/details/",
                    view=views.ajax_fleet_details,
                    name="ajax_fleet_details",
                ),
                path(
                    route="fleet/<int:fleet_id>/member/kick/",
                    view=views.ajax_fleet_kick_member,
                    name="ajax_fleet_kick_member",
                ),
            ]
        ),
    ),
]
