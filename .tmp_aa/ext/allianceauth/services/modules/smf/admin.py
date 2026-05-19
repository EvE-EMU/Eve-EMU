from django.contrib import admin

from ...admin import ServicesUserAdmin
from .models import SmfUser


@admin.register(SmfUser)
class SmfUserAdmin(ServicesUserAdmin):
    list_display = ServicesUserAdmin.list_display + ('username',)
    search_fields = ServicesUserAdmin.search_fields + ('username', )
