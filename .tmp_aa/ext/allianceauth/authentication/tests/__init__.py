from unittest import mock

from django.urls import reverse

MODULE_PATH = 'allianceauth.authentication'


def patch(target, *args, **kwargs):
    return mock.patch(f'{MODULE_PATH}{target}', *args, **kwargs)


def get_admin_change_view_url(obj: object) -> str:
    """returns URL to admin change view for given object"""
    return reverse(
        f'admin:{obj._meta.app_label}_{type(obj).__name__.lower()}_change',
        args=(obj.pk,)
    )


def get_admin_search_url(ModelClass: type) -> str:
    """returns URL to search URL for model of given object"""
    return '{}{}/'.format(
        reverse('admin:app_list', args=(ModelClass._meta.app_label,)),
        ModelClass.__name__.lower()
    )
