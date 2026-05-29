from django.urls import path

from . import views

app_name = "moon_rentals"

urlpatterns = [
    path("schedule/", views.schedule_list, name="schedule"),
    path("import/", views.import_page, name="import"),
    path("pop/<int:pop_id>/", views.pop_detail, name="pop_detail"),
    path("pop/<int:pop_id>/refresh/", views.pop_refresh, name="pop_refresh"),
]
