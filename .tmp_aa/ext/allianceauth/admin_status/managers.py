from typing import TYPE_CHECKING

from django.db import models

from allianceauth.admin_status.hooks import (
    Announcement,
    get_all_applications_announcements,
)
from allianceauth.services.hooks import get_extension_logger

if TYPE_CHECKING:
    from .models import ApplicationAnnouncement

logger = get_extension_logger(__name__)

class ApplicationAnnouncementManager(models.Manager):

    def sync_and_return(self):
        """
        Checks all hooks if new notifications need to be created.
        Return all notification objects after
        """
        logger.info("Syncing announcements")
        current_announcements = get_all_applications_announcements()
        self._delete_obsolete_announcements(current_announcements)
        self._store_new_announcements(current_announcements)

        return self.all()

    def _delete_obsolete_announcements(self, current_announcements: list[Announcement]):
        """Deletes all announcements stored in the database that aren't retrieved anymore"""
        hashes = [announcement.get_hash() for announcement in current_announcements]
        self.exclude(announcement_hash__in=hashes).delete()

    def _store_new_announcements(self, current_announcements: list[Announcement]):
        """Stores a new database object for new application announcements"""

        for current_announcement in current_announcements:
            try:
                announcement = self.get(announcement_hash=current_announcement.get_hash())
            except self.model.DoesNotExist:
                self.create_from_announcement(current_announcement)
            else:
                # if exists update the text only
                if announcement.announcement_text != current_announcement.announcement_text:
                    announcement.announcement_text = current_announcement.announcement_text
                    announcement.save()

    def create_from_announcement(self, announcement: Announcement) -> "ApplicationAnnouncement":
        """Creates from the Announcement dataclass"""
        return self.create(
            application_name=announcement.application_name,
            announcement_number=announcement.announcement_number,
            announcement_text=announcement.announcement_text,
            announcement_url=announcement.announcement_url,
            announcement_hash=announcement.get_hash(),
        )
