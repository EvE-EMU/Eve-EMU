from django.contrib import admin

from ...admin import ServicesUserAdmin
from .models import DiscourseUser


@admin.register(DiscourseUser)
class DiscourseUserAdmin(ServicesUserAdmin):
    list_display = ServicesUserAdmin.list_display + (
        'enabled',
    )
