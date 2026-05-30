from django.utils.translation import gettext_lazy as _

from allianceauth import hooks
from allianceauth.services.hooks import MenuItemHook, UrlHook

from . import urls


class MoonTsarMenuItem(MenuItemHook):
    def __init__(self):
        MenuItemHook.__init__(
            self,
            _("Moon Tsar"),
            "fas fa-moon",
            "moon_tsar:dashboard",
            navactive=["moon_tsar:"],
        )

    def render(self, request):
        if request.user.has_perm("moon_tsar.view_dashboard") or request.user.has_perm(
            "moon_tsar.view_own_bills"
        ):
            return MenuItemHook.render(self, request)
        return ""


@hooks.register("menu_item_hook")
def register_menu():
    return MoonTsarMenuItem()


@hooks.register("url_hook")
def register_urls():
    return UrlHook(urls, "moon_tsar", r"^moon-tsar/")
