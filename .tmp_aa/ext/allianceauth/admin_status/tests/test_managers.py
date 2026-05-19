from unittest.mock import patch

from allianceauth.admin_status.hooks import Announcement
from allianceauth.admin_status.models import ApplicationAnnouncement
from allianceauth.utils.testing import NoSocketsTestCase

MODULE_PATH = 'allianceauth.admin_status.managers'

DEFAULT_ANNOUNCEMENTS = [
    Announcement(
        application_name="Test GitHub Application",
        announcement_number=1,
        announcement_text="GitHub issue",
        announcement_url="https://github.com/r0kym/test/issues/1",
    ),
    Announcement(
        application_name="Test Gitlab Application",
        announcement_number=1,
        announcement_text="GitLab issue",
        announcement_url="https://gitlab.com/r0kym/allianceauth-example-plugin/-/issues/1",
    )
]

class TestSyncManager(NoSocketsTestCase):

    def setUp(self):
        ApplicationAnnouncement.object.create(
            application_name="Test GitHub Application",
            announcement_number=1,
            announcement_text="GitHub issue",
            announcement_url="https://github.com/r0kym/test/issues/1",
            announcement_hash="9dbedb9c47529bb43cfecb704768a35d085b145930e13cced981623e5f162a85",
        )
        ApplicationAnnouncement.object.create(
            application_name="Test Gitlab Application",
            announcement_number=1,
            announcement_text="GitLab issue",
            announcement_url="https://gitlab.com/r0kym/allianceauth-example-plugin/-/issues/1",
            announcement_hash="8955a9c12a1cfa9e1776662bdaf111147b84e35c79f24bfb758e35333a18b1bd",
        )

    @patch(MODULE_PATH + '.get_all_applications_announcements')
    def test_announcements_stay_as_is(self, all_announcements_mocker):
        # given
        announcement_ids = set(ApplicationAnnouncement.object.values_list("id", flat=True))
        all_announcements_mocker.return_value = DEFAULT_ANNOUNCEMENTS
        # when
        ApplicationAnnouncement.object.sync_and_return()
        # then
        self.assertEqual(ApplicationAnnouncement.object.count(), 2)
        self.assertEqual(set(ApplicationAnnouncement.object.values_list("id", flat=True)), announcement_ids)

    @patch(MODULE_PATH + '.get_all_applications_announcements')
    def test_announcement_add(self, all_announcements_mocker):
        # given
        returned_announcements = DEFAULT_ANNOUNCEMENTS + [Announcement(application_name="Test Application", announcement_number=1, announcement_text="New test announcement", announcement_url="https://example.com")]
        all_announcements_mocker.return_value = returned_announcements
        # when
        ApplicationAnnouncement.object.sync_and_return()
        # then
        self.assertEqual(ApplicationAnnouncement.object.count(), 3)
        self.assertTrue(ApplicationAnnouncement.object.filter(application_name="Test Application", announcement_number=1, announcement_text="New test announcement", announcement_url="https://example.com"))

    @patch(MODULE_PATH + '.get_all_applications_announcements')
    def test_announcement_remove(self, all_announcements_mocker):
        # given
        all_announcements_mocker.return_value = DEFAULT_ANNOUNCEMENTS
        ApplicationAnnouncement.object.sync_and_return()
        self.assertEqual(ApplicationAnnouncement.object.count(), 2)
        all_announcements_mocker.return_value = DEFAULT_ANNOUNCEMENTS[:1]
        # when
        ApplicationAnnouncement.object.sync_and_return()
        # then
        self.assertEqual(ApplicationAnnouncement.object.count(), 1)
        self.assertTrue(ApplicationAnnouncement.object.filter(application_name="Test GitHub Application").exists())
