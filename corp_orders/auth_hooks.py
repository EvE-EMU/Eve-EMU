from django.utils.translation import gettext_lazy as _

from allianceauth import hooks
from allianceauth.services.hooks import MenuItemHook, UrlHook

from corp_orders import urls


class CorpOrdersMenuItem(MenuItemHook):
    def __init__(self):
        super().__init__(
            _("Corp stock orders"),
            "fa-solid fa-truck-ramp-box",
            "corp_orders:order_quote",
            navactive=["corp_orders:"],
        )

    def render(self, request):
        if request.user.has_perm("corp_orders.create_order"):
            return MenuItemHook.render(self, request)
        return ""


@hooks.register("menu_item_hook")
def register_menu():
    return CorpOrdersMenuItem()


@hooks.register("url_hook")
def register_urls():
    return UrlHook(urls, "corp_orders", r"^corp-orders/")
