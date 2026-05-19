from django.urls import path

from . import views

app_name = "industry"

urlpatterns = [
    path("", views.index, name="index"),
    path("select", views.char_selector, name="selector"),
    path("jobs/<character_id>", views.list_jobs, name="list_jobs"),
    # path("delete/<pk>/", views.UserTokenDelete.as_view(), name="character-delete"),
]
