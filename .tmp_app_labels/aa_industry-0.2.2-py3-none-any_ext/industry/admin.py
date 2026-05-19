from django.contrib import admin

from .models import Facility, UserCharacters


@admin.register(Facility)
class FacilityAdmin(admin.ModelAdmin):
    list_display = ['name', 'facility_id', 'solar_system', 'owner_id']


@admin.register(UserCharacters)
class UserCharactersAdmin(admin.ModelAdmin):
    list_display = ['user', 'character_ownership']
