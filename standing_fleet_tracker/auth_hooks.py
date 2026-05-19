from django.utils.translation import gettext_lazy as _

from allianceauth import hooks
from allianceauth.services.hooks import MenuItemHook, UrlHook

from standing_fleet_tracker import urls


class StandingFleetMenuItem(MenuItemHook):
    def __init__(self):
        super().__init__(
            _("Standing Fleet"),
            "fa-solid fa-users-rays",
            "standing_fleet_tracker:leaderboard",
            navactive=["standing_fleet_tracker:"],
        )

    def render(self, request):
        if request.user.has_perm("standing_fleet_tracker.basic_access"):
            return MenuItemHook.render(self, request)
        return ""


@hooks.register("menu_item_hook")
def register_menu():
    return StandingFleetMenuItem()


@hooks.register("url_hook")
def register_urls():
    return UrlHook(urls, "standing_fleet_tracker", r"^standing-fleet/")


@hooks.register("charlink")
def register_charlink_hook():
    return "standing_fleet_tracker.charlink_hook"
