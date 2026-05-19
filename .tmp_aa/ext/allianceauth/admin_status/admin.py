"""Admin site for admin status applicaton"""
from django.contrib import admin

from allianceauth.admin_status.models import ApplicationAnnouncement


@admin.register(ApplicationAnnouncement)
class ApplicationAnnouncementAdmin(admin.ModelAdmin):
    list_display = ["application_name", "announcement_number", "announcement_text", "hide_announcement"]
    list_filter = ["hide_announcement"]
    ordering = ["application_name", "announcement_number"]
    readonly_fields = ["application_name", "announcement_number", "announcement_text", "announcement_url"]
    fields = ["application_name", "announcement_number", "announcement_text", "announcement_url", "hide_announcement"]

    def has_add_permission(self, request):
        return False

    def has_delete_permission(self, request, obj=None):
        return False
