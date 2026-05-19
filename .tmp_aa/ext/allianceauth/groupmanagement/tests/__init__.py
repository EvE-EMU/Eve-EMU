from django.urls import reverse


def get_admin_change_view_url(obj: object) -> str:
    return reverse(
        f'admin:{obj._meta.app_label}_{type(obj).__name__.lower()}_change',
        args=(obj.pk,)
    )
