from django.apps import AppConfig
from django.utils.translation import gettext_lazy as _


class MoonRentalsConfig(AppConfig):
    name = "moonmining.rentals"
    label = "moonrentals"
    verbose_name = _("Moon Rentals")
