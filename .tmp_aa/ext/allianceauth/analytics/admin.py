from solo.admin import SingletonModelAdmin

from django.contrib import admin

from .models import AnalyticsIdentifier, AnalyticsTokens


@admin.register(AnalyticsIdentifier)
class AnalyticsIdentifierAdmin(SingletonModelAdmin):
    readonly_fields = ['identifier', ]



@admin.register(AnalyticsTokens)
class AnalyticsTokensAdmin(admin.ModelAdmin):
    search_fields = ['name', ]
    list_display = ['name', 'type', ]
