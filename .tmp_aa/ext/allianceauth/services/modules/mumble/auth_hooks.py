import logging
import urllib

from django.conf import settings
from django.template.loader import render_to_string
from django.utils.translation import gettext_lazy as _

from allianceauth import hooks
from allianceauth.menu.hooks import MenuItemHook
from allianceauth.notifications import notify
from allianceauth.services.hooks import ServicesHook, UrlHook

from . import urls
from .models import MumbleUser
from .tasks import MumbleTasks

logger = logging.getLogger(__name__)


class MumbleService(ServicesHook):
    def __init__(self):
        ServicesHook.__init__(self)
        self.name = 'mumble'
        # self.urlpatterns = urlpatterns  # Migrated intentionally to URLHook to allow for excluded views
        self.service_url = settings.MUMBLE_URL
        self.access_perm = 'mumble.access_mumble'
        self.service_ctrl_template = 'services/mumble/mumble_service_ctrl.html'
        self.name_format = '[{corp_ticker}]{character_name}'

    def delete_user(self, user, notify_user=False):
        logging.debug(f"Deleting user {user} {self.name} account")
        try:
            if user.mumble.delete():
                if notify_user:
                    notify(user, 'Mumble Account Disabled', level='danger')
                return True
            return False
        except MumbleUser.DoesNotExist:
            logging.debug("User does not have a mumble account")

    def validate_user(self, user):
        if MumbleTasks.has_account(user) and not self.service_active_for_user(user):
            self.delete_user(user, notify_user=True)

    def update_all_groups(self):
        logger.debug(f"Updating all {self.name} groups")
        MumbleTasks.update_all_groups.delay()

    def service_active_for_user(self, user):
        return user.has_perm(self.access_perm)

    def render_services_ctrl(self, request):
        urls = self.Urls()
        urls.auth_activate = 'mumble:activate'
        urls.auth_deactivate = 'mumble:deactivate'
        urls.auth_reset_password = 'mumble:reset_password'
        urls.auth_set_password = 'mumble:set_password'

        return render_to_string(self.service_ctrl_template, {
            'service_name': self.title,
            'urls': urls,
            'service_url': self.service_url,
            'connect_url': urllib.parse.quote(request.user.mumble.username, safe="") + '@' + self.service_url if MumbleTasks.has_account(request.user) else self.service_url,
            'username': request.user.mumble.username if MumbleTasks.has_account(request.user) else '',
        }, request=request)


@hooks.register('services_hook')
def register_mumble_service() -> ServicesHook:
    return MumbleService()


class MumbleMenuItem(MenuItemHook):
    def __init__(self) -> None:
        MenuItemHook.__init__(
            self=self,
            text=_("Mumble Temp Links"),
            classes="fa-solid fa-microphone",
            url_name="mumble:templinks",
            navactive=["mumble:templinks"],
        )

    def render(self, request) -> str:
        if request.user.has_perm("mumble.create_new_templinks"):
            return MenuItemHook.render(self, request)
        return ""


@hooks.register("menu_item_hook")
def register_menu() -> MumbleMenuItem:
    return MumbleMenuItem()

@hooks.register("url_hook")
def register_urls() -> UrlHook:
    return UrlHook(
        urls,
        "mumble",
        r"^mumble/",
        excluded_views=[
            "allianceauth.services.modules.mumble.views.link",
            "allianceauth.services.modules.mumble.views.link_sso"
        ])
