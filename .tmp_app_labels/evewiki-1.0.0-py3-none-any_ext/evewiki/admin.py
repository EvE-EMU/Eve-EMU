"""Admin site."""

from django.contrib import admin

from .models.logs import Log
from .models.page_versions import PageVersion
from .models.pages import Page
from .models.settings import Setting

# from django.contrib import admin

# Register your models for the admin site here.
admin.site.register(Page)
admin.site.register(Setting)
admin.site.register(PageVersion)
admin.site.register(Log)
