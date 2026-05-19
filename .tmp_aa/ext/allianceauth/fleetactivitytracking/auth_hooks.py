from django.utils.translation import gettext_lazy as _

from allianceauth import hooks
from allianceauth.menu.hooks import MenuItemHook
from allianceauth.services.hooks import UrlHook

from . import urls


@hooks.register('menu_item_hook')
def register_menu() -> MenuItemHook:
    return MenuItemHook(_('Fleet Activity Tracking'), 'fa-solid fa-users', 'fatlink:view',
                        navactive=['fatlink:'])


@hooks.register('url_hook')
def register_url() -> UrlHook:
    return UrlHook(urls, 'fatlink', r'^fat/')
