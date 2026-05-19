from django.urls import path

from standing_fleet_tracker import views

app_name = "standing_fleet_tracker"

urlpatterns = [
    path("", views.dashboard, name="dashboard"),
    path("leaderboard/", views.leaderboard, name="leaderboard"),
    path("lagging/", views.lagging_board, name="lagging_board"),
    path("character/<int:character_id>/", views.character_detail, name="character_detail"),
    path("session/<int:session_id>/", views.session_detail, name="session_detail"),
    path("api/ship-fit/<int:ship_type_id>/", views.ship_fit_json, name="ship_fit_json"),
    path(
        "character/<int:character_id>/kpi/",
        views.character_monthly_kpi,
        name="character_monthly_kpi",
    ),
    path("user/<int:user_id>/", views.user_detail, name="user_detail"),
]
