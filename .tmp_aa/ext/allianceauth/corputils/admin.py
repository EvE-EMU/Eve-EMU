from django.contrib import admin

from .models import CorpMember, CorpStats

admin.site.register(CorpStats)
admin.site.register(CorpMember)
