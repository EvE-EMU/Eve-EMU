from django.db import models
from django.utils.translation import gettext_lazy as _

from allianceauth.admin_status.managers import ApplicationAnnouncementManager


class ApplicationAnnouncement(models.Model):
    """
    Announcement originating from an application
    """
    object = ApplicationAnnouncementManager()

    application_name = models.CharField(max_length=50, help_text=_("Name of the application that issued the announcement"))
    announcement_number = models.IntegerField(help_text=_("Issue number on the notification source"))
    announcement_text = models.TextField(max_length=300, help_text=_("Issue title text displayed on the dashboard"))
    announcement_url = models.TextField(max_length=200)

    announcement_hash = models.CharField(
        max_length=64,
        default=None,
        unique=True,
        editable=False,
        help_text="hash of an announcement."
    )

    hide_announcement = models.BooleanField(
        default=False,
        help_text=_("Set to true if the announcement should not be displayed on the dashboard")
    )

    class Meta:
        # Should be updated to a composite key when the switch to Django 5.2 is made
        # https://docs.djangoproject.com/en/5.2/topics/composite-primary-key/
        constraints = [
            models.UniqueConstraint(
                fields=["application_name", "announcement_number"], name="functional_pk_applicationissuenumber"
            )
        ]

    def __str__(self):
        return f"{self.application_name} announcement #{self.announcement_number}"

    def is_hidden(self) -> bool:
        """Function in case rules are made in the future to force hide/force show some announcements"""
        return self.hide_announcement
