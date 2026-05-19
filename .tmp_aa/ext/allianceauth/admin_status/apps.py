# Django
from django.apps import AppConfig
from django.utils.translation import gettext_lazy as _


class AdminStatusApplication(AppConfig):
    name = 'allianceauth.admin_status'
    label = 'admin_status'
    verbose_name = _("Admin Status")
