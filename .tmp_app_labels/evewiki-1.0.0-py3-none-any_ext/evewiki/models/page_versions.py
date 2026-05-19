from django.db import models

from allianceauth.authentication.models import UserProfile

from .pages import Page
from .settings import Setting


class PageVersion(models.Model):
    """
    Previous edits have value
    """

    page = models.ForeignKey(
        Page,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        help_text="Page being edited",
    )

    user = models.ForeignKey(
        UserProfile,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        help_text="User editing the page",
    )

    content = models.TextField(default="", blank=True, null=True)

    created = models.DateTimeField(auto_now_add=True)

    def save(self, *args, **kwargs):
        """
        Clean up old versions when saving
        """
        super().save(*args, **kwargs)
        if self.page_id:
            # Get the IDs of old versions to delete
            settings = Setting.get_settings()
            old_version_ids = list(
                PageVersion.objects.filter(page=self.page)
                .order_by("-created")
                .values_list("id", flat=True)[settings.max_versions :]
            )
            if old_version_ids:
                PageVersion.objects.filter(id__in=old_version_ids).delete()
