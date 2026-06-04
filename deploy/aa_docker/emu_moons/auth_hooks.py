from django.utils.translation import gettext_lazy as _

from allianceauth import hooks
from allianceauth.services.hooks import MenuItemHook, UrlHook

from . import urls


class EmuMoonsMenuItem(MenuItemHook):
    def __init__(self):
        MenuItemHook.__init__(
            self,
            _("EMU Moons"),
            "fas fa-moon",
            "emu_moons:index",
            navactive=["emu_moons:"],
        )

    def render(self, request):
        return MenuItemHook.render(self, request)


@hooks.register("menu_item_hook")
def register_menu():
    return EmuMoonsMenuItem()


@hooks.register("url_hook")
def register_urls():
    return UrlHook(urls, "emu_moons", r"^emu-moons/")


@hooks.register("url_hook")
def register_charlink_audit_redirect():
    from . import charlink_urls

    return UrlHook(
        charlink_urls,
        "emu_moons_charlink",
        r"^charlink/audit/app/emu_moons_corpminingobserver/",
    )


@hooks.register("charlink")
def register_charlink_hook():
    return "emu_moons.charlink_hook"
