"""Routes."""

from django.urls import path, re_path

from evewiki import views

app_name = "evewiki"

urlpatterns = [
    path("", views.index, name="index"),
    path("page", views.page, name="page"),
    path("page_delete", views.page_delete, name="page_delete"),
    # Catch all URLs starting with 'public'
    re_path(r"^public(?:/(?P<public_path>.*))?$", views.public, name="public"),
    # Send unknown routes to the index and seach for the slug
    re_path(r"^(?P<unknown_path>.*)$", views.index),
]
