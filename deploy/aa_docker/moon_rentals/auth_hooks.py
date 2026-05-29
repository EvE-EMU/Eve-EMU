from django.utils.translation import gettext_lazy as _

from allianceauth import hooks
from allianceauth.services.hooks import MenuItemHook, UrlHook

from . import urls


class MoonScheduleMenuItem(MenuItemHook):
    def __init__(self):
        MenuItemHook.__init__(
            self,
            _("Moon schedule"),
            "fas fa-calendar-alt",
            "moon_rentals:schedule",
            navactive=["moon_rentals:"],
        )

    def render(self, request):
        if request.user.has_perm("miningtaxes.auditor_access") or request.user.has_perm(
            "moon_rentals.view_schedule"
        ):
            return MenuItemHook.render(self, request)
        return ""


@hooks.register("menu_item_hook")
def register_menu():
    return MoonScheduleMenuItem()


@hooks.register("url_hook")
def register_urls():
    return UrlHook(urls, "moon_rentals", r"^miningtaxes/")
