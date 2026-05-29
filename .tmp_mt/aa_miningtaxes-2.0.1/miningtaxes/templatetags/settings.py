from django import template

from ..app_settings import MININGTAXES_ALLOW_ANALYTICS

register = template.Library()


@register.simple_tag
def analytics():
    return MININGTAXES_ALLOW_ANALYTICS
