from allianceauth import hooks
from allianceauth.services.hooks import MenuItemHook, UrlHook
from django.utils.translation import gettext_lazy as _
from .models import Event
from django.db.models import Q
from django.utils import timezone
from .app_settings import OPCALENDAR_SHOW_EVENT_COUNTER

from . import urls


class OpcalendarMenuItem(MenuItemHook):
    """This class ensures only authorized users will see the menu entry"""

    def __init__(self):
        # setup menu entry for sidebar
        MenuItemHook.__init__(
            self,
            _("Operation Calendar"),
            "far fa-calendar-alt",
            "opcalendar:calendar",
            navactive=["opcalendar:calendar"],
        )

    def render(self, request):
        if request.user.has_perm("opcalendar.basic_access"):
            if OPCALENDAR_SHOW_EVENT_COUNTER:
                # Get the user's main character
                user_main_character = request.user.profile.main_character
                # Get the current time
                now = timezone.now()
                # Count future events without signups for the current user's main character and where event.external is False
                self.count = (
                    Event.objects.filter(
                        Q(eventmember__isnull=True)
                        | ~Q(eventmember__character=user_main_character),
                        external=False,
                        start_time__gte=now,
                    )
                    .distinct()
                    .count()
                )
            return MenuItemHook.render(self, request)
        return ""


@hooks.register("menu_item_hook")
def register_menu():
    return OpcalendarMenuItem()


@hooks.register("url_hook")
def register_urls():
    return UrlHook(
        urls,
        "opcalendar",
        r"^opcalendar/",
        excluded_views=["opcalendar.views.EventFeed"],
    )


@hooks.register("discord_cogs_hook")
def register_cogs():
    return ["opcalendar.cogs.ops"]
