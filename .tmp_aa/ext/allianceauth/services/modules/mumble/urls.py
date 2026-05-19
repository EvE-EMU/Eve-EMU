from django.urls import path, re_path

from . import views

app_name = 'mumble'

urlpatterns = [
    # Mumble service control
    path('activate/', views.CreateAccountMumbleView.as_view(), name='activate'),
    path('deactivate/', views.DeleteMumbleView.as_view(), name='deactivate'),
    path('reset_password/', views.ResetPasswordMumbleView.as_view(), name='reset_password'),
    path('set_password/', views.SetPasswordMumbleView.as_view(), name='set_password'),
    path('connection_history/', views.connection_history, name="connection_history"),
    path('ajax/connection_history_data', views.connection_history_data, name="connection_history_data"),
    path('ajax/release_counts_data', views.release_counts_data, name="release_counts_data"),
    path('ajax/release_pie_chart_data', views.release_pie_chart_data, name="release_pie_chart_data"),
    # Temp Links
    path("templinks/", views.templinks, name="templinks"),
    re_path(r"^join/(?P<link_ref>[\w\-]+)/$", views.link, name="join"),
    re_path(r"^nuke/(?P<link_ref>[\w\-]+)/$", views.nuke, name="nuke"),
]
