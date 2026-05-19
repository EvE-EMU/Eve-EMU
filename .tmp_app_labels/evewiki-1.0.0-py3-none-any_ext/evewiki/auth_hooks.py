from django.utils.translation import gettext_lazy as _

from allianceauth import hooks
from allianceauth.services.hooks import MenuItemHook, UrlHook

from evewiki import urls


class EveWikiMenuItem(MenuItemHook):
    """This class ensures only authorized users will see the menu entry"""

    def __init__(self):
        # setup menu entry for sidebar
        MenuItemHook.__init__(
            self,
            _("Wiki"),
            "fas fa-tree fa-fw",
            "evewiki:index",
            navactive=["evewiki:"],
        )

    def render(self, request):
        if request.user.has_perm("evewiki.basic_access"):
            return MenuItemHook.render(self, request)
        return ""


@hooks.register("menu_item_hook")
def register_menu():
    return EveWikiMenuItem()


@hooks.register("url_hook")
def register_urls():
    return UrlHook(
        urls,
        "evewiki",
        r"^evewiki/",
        excluded_views=["evewiki.views.public"],
    )
