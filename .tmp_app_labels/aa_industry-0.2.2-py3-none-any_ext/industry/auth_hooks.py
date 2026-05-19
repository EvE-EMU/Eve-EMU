from django.utils.translation import gettext as _

from allianceauth import hooks
from allianceauth.services.hooks import MenuItemHook, UrlHook

from . import urls


class IndustryMenuItem(MenuItemHook):
    """ This class ensures only authorized users will see the menu entry """

    def __init__(self):
        # setup menu entry for sidebar
        MenuItemHook.__init__(
            self,
            _("Industry"),
            # "fas fa-cube fa-fw",
            "fas fa-industry",
            "industry:index",
            navactive=["industry:"],
        )

    def render(self, request):
        if request.user.has_perm("industry.view_industry"):
            return MenuItemHook.render(self, request)
        return ""


@hooks.register("menu_item_hook")
def register_menu():
    return IndustryMenuItem()


@hooks.register("url_hook")
def register_urls():
    return UrlHook(urls, "industry", r"^industry/")
