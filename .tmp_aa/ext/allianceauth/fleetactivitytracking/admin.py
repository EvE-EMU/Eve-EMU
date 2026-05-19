from django.contrib import admin

from allianceauth.fleetactivitytracking.models import Fat, Fatlink

admin.site.register(Fatlink)
admin.site.register(Fat)
