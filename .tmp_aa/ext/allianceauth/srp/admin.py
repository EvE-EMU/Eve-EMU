from django.contrib import admin

from allianceauth.srp.models import SrpFleetMain, SrpUserRequest

admin.site.register(SrpFleetMain)
admin.site.register(SrpUserRequest)
