from django.contrib import admin

from ...admin import ServicesUserAdmin
from .models import Phpbb3User


@admin.register(Phpbb3User)
class Phpbb3UserAdmin(ServicesUserAdmin):
    list_display = ServicesUserAdmin.list_display + ('username',)
    search_fields = ServicesUserAdmin.search_fields + ('username', )
