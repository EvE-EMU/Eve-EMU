from django.apps import AppConfig

from . import __version__


class MailrelayConfig(AppConfig):
    name = "mailrelay"
    label = "mailrelay"
    verbose_name = f"Mail Relay v{__version__}"
