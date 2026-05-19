from django.utils.translation import gettext_lazy as _

from allianceauth import hooks
from allianceauth.services.hooks import MenuItemHook, UrlHook

from buyback_v2 import urls


class PublicBuybackMenuItem(MenuItemHook):
    def __init__(self):
        super().__init__(
            _("Public buyback prices"),
            "fa-solid fa-calculator",
            "buyback_v2:public_index",
            navactive=["buyback_v2:"],
        )

    def render(self, request):
        return MenuItemHook.render(self, request)


@hooks.register("menu_item_hook")
def register_public_menu():
    return PublicBuybackMenuItem()


@hooks.register("url_hook")
def register_urls():
    return UrlHook(
        urls,
        "buyback_v2",
        r"^buyback-public/",
        excluded_views=[
            "buyback_v2.views.public_index",
            "buyback_v2.views.public_program_calculate",
        ],
    )
