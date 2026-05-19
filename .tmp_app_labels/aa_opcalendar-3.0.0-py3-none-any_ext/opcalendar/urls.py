from django.urls import path

from . import views

app_name = "opcalendar"
urlpatterns = [
    path("index", views.index, name="index"),
    path("", views.CalendarView.as_view(), name="calendar"),
    path("event/new/", views.create_event, name="event_new"),
    path("add_ingame_calendar/", views.add_ingame_calendar, name="add_ingame_calendar"),
    path("event/edit/<int:event_id>/", views.EventEdit, name="event_edit"),
    path("event/<int:event_id>/details/", views.event_details, name="event-detail"),
    path(
        "ingame/event/<int:event_id>/details/",
        views.ingame_event_details,
        name="ingame-event-detail",
    ),
    path(
        "add_eventmember/<int:event_id>",
        views.EventMemberSignup,
        name="event_member_signup",
    ),
    path("event/<int:event_id>/remove", views.EventDeleteView, name="remove_event"),
    path(
        "remove_eventmember/<int:event_id>",
        views.EventMemberRemove,
        name="event_member_remove",
    ),
    path("feed.ics", views.EventFeed()),
    path(
        "event/<int:event_id>/details/feed.ics",
        views.EventIcalView(),
        name="event-ical-view",
    ),
    path("event/new/ajax/get_category/", views.get_category, name="get_category"),
    path(
        "event/<int:event_id>/signup/attending/",
        views.event_member_signup_attending,
        name="event_member_signup_attending",
    ),
    path(
        "event/<int:event_id>/signup/maybe/",
        views.event_member_signup_maybe,
        name="event_member_signup_maybe",
    ),
    path(
        "event/<int:event_id>/signup/declined/",
        views.event_member_signup_declined,
        name="event_member_signup_declined",
    ),
    path(
        "event/<int:event_id>/remove/",
        views.event_member_remove,
        name="event_member_remove",
    ),
    path("user/settings/", views.user_settings_view, name="user_settings"),
]
