from django.utils.translation import gettext_lazy as _

from allianceauth import hooks
from allianceauth.services.hooks import MenuItemHook, UrlHook

from . import urls


class MoonOreReportMenuItem(MenuItemHook):
    def __init__(self):
        MenuItemHook.__init__(
            self,
            _("Moon ore report"),
            "fas fa-moon",
            "miningtaxes_ext:moon_ore_report",
            navactive=["miningtaxes_ext:"],
        )

    def render(self, request):
        if request.user.has_perm("miningtaxes.auditor_access"):
            return MenuItemHook.render(self, request)
        return ""


@hooks.register("menu_item_hook")
def register_moon_ore_menu():
    return MoonOreReportMenuItem()


@hooks.register("url_hook")
def register_urls():
    return UrlHook(urls, "miningtaxes_ext", r"^miningtaxes/")

