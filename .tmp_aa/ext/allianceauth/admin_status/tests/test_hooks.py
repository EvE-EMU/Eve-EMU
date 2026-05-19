import requests_mock

from allianceauth.admin_status.hooks import Announcement
from allianceauth.services.hooks import AppAnnouncementHook
from allianceauth.utils.testing import NoSocketsTestCase


class TestHooks(NoSocketsTestCase):

    @requests_mock.mock()
    def test_fetch_gitlab(self, requests_mocker):
        # given
        announcement_hook = AppAnnouncementHook("test GitLab app", "r0kym/allianceauth-example-plugin",
                                                AppAnnouncementHook.Service.GITLAB)
        requests_mocker.get(
            "https://gitlab.com/api/v4/projects/r0kym%2Fallianceauth-example-plugin/issues?labels=announcement&state=opened",
            json=[
                {
                    "id": 166279127,
                    "iid": 1,
                    "project_id": 67653102,
                    "title": "Test GitLab issue",
                    "description": "Test issue",
                    "state": "opened",
                    "created_at": "2025-04-20T21:26:57.914Z",
                    "updated_at": "2025-04-21T11:04:30.501Z",
                    "closed_at": None,
                    "closed_by": None,
                    "labels": [
                        "announcement"
                    ],
                    "milestone": None,
                    "assignees": [],
                    "author": {
                        "id": 14491514,
                        "username": "r0kym",
                        "public_email": "",
                        "name": "T'rahk Rokym",
                        "state": "active",
                        "locked": False,
                        "avatar_url": "https://gitlab.com/uploads/-/system/user/avatar/14491514/avatar.png",
                        "web_url": "https://gitlab.com/r0kym"
                    },
                    "type": "ISSUE",
                    "assignee": None,
                    "user_notes_count": 0,
                    "merge_requests_count": 0,
                    "upvotes": 0,
                    "downvotes": 0,
                    "due_date": None,
                    "confidential": False,
                    "discussion_locked": None,
                    "issue_type": "issue",
                    "web_url": "https://gitlab.com/r0kym/allianceauth-example-plugin/-/issues/1",
                    "time_stats": {
                        "time_estimate": 0,
                        "total_time_spent": 0,
                        "human_time_estimate": None,
                        "human_total_time_spent": None
                    },
                    "task_completion_status": {
                        "count": 0,
                        "completed_count": 0
                    },
                    "blocking_issues_count": 0,
                    "has_tasks": True,
                    "task_status": "0 of 0 checklist items completed",
                    "_links": {
                        "self": "https://gitlab.com/api/v4/projects/67653102/issues/1",
                        "notes": "https://gitlab.com/api/v4/projects/67653102/issues/1/notes",
                        "award_emoji": "https://gitlab.com/api/v4/projects/67653102/issues/1/award_emoji",
                        "project": "https://gitlab.com/api/v4/projects/67653102",
                        "closed_as_duplicate_of": None
                    },
                    "references": {
                        "short": "#1",
                        "relative": "#1",
                        "full": "r0kym/allianceauth-example-plugin#1"
                    },
                    "severity": "UNKNOWN",
                    "moved_to_id": None,
                    "imported": False,
                    "imported_from": "none",
                    "service_desk_reply_to": None
                }
            ]
        )
        # when
        announcements = announcement_hook.get_announcement_list()
        # then
        self.assertEqual(len(announcements), 1)
        self.assertIn(Announcement(
            application_name="test GitLab app",
            announcement_url="https://gitlab.com/r0kym/allianceauth-example-plugin/-/issues/1",
            announcement_number=1,
            announcement_text="Test GitLab issue"
        ), announcements)

    @requests_mock.mock()
    def test_fetch_github(self, requests_mocker):
        # given
        announcement_hook = AppAnnouncementHook("test GitHub app", "r0kym/test", AppAnnouncementHook.Service.GITHUB)
        requests_mocker.get(
            "https://api.github.com/repos/r0kym/test/issues?labels=announcement",
            json=[
                {
                    "url": "https://api.github.com/repos/r0kym/test/issues/1",
                    "repository_url": "https://api.github.com/repos/r0kym/test",
                    "labels_url": "https://api.github.com/repos/r0kym/test/issues/1/labels{/name}",
                    "comments_url": "https://api.github.com/repos/r0kym/test/issues/1/comments",
                    "events_url": "https://api.github.com/repos/r0kym/test/issues/1/events",
                    "html_url": "https://github.com/r0kym/test/issues/1",
                    "id": 3007269496,
                    "node_id": "I_kwDOOc2YvM6zP0p4",
                    "number": 1,
                    "title": "GitHub issue",
                    "user": {
                        "login": "r0kym",
                        "id": 56434393,
                        "node_id": "MDQ6VXNlcjU2NDM0Mzkz",
                        "avatar_url": "https://avatars.githubusercontent.com/u/56434393?v=4",
                        "gravatar_id": "",
                        "url": "https://api.github.com/users/r0kym",
                        "html_url": "https://github.com/r0kym",
                        "followers_url": "https://api.github.com/users/r0kym/followers",
                        "following_url": "https://api.github.com/users/r0kym/following{/other_user}",
                        "gists_url": "https://api.github.com/users/r0kym/gists{/gist_id}",
                        "starred_url": "https://api.github.com/users/r0kym/starred{/owner}{/repo}",
                        "subscriptions_url": "https://api.github.com/users/r0kym/subscriptions",
                        "organizations_url": "https://api.github.com/users/r0kym/orgs",
                        "repos_url": "https://api.github.com/users/r0kym/repos",
                        "events_url": "https://api.github.com/users/r0kym/events{/privacy}",
                        "received_events_url": "https://api.github.com/users/r0kym/received_events",
                        "type": "User",
                        "user_view_type": "public",
                        "site_admin": False
                    },
                    "labels": [
                        {
                            "id": 8487814480,
                            "node_id": "LA_kwDOOc2YvM8AAAAB-enFUA",
                            "url": "https://api.github.com/repos/r0kym/test/labels/announcement",
                            "name": "announcement",
                            "color": "aaaaaa",
                            "default": False,
                            "description": None
                        }
                    ],
                    "state": "open",
                    "locked": False,
                    "assignee": None,
                    "assignees": [],
                    "milestone": None,
                    "comments": 0,
                    "created_at": "2025-04-20T22:41:10Z",
                    "updated_at": "2025-04-21T11:05:08Z",
                    "closed_at": None,
                    "author_association": "OWNER",
                    "active_lock_reason": None,
                    "sub_issues_summary": {
                        "total": 0,
                        "completed": 0,
                        "percent_completed": 0
                    },
                    "body": None,
                    "closed_by": None,
                    "reactions": {
                        "url": "https://api.github.com/repos/r0kym/test/issues/1/reactions",
                        "total_count": 0,
                        "+1": 0,
                        "-1": 0,
                        "laugh": 0,
                        "hooray": 0,
                        "confused": 0,
                        "heart": 0,
                        "rocket": 0,
                        "eyes": 0
                    },
                    "timeline_url": "https://api.github.com/repos/r0kym/test/issues/1/timeline",
                    "performed_via_github_app": None,
                    "state_reason": None
                }
            ]
        )
        # when
        announcements = announcement_hook.get_announcement_list()
        # then
        self.assertEqual(len(announcements), 1)
        self.assertIn(Announcement(
            application_name="test GitHub app",
            announcement_url="https://github.com/r0kym/test/issues/1",
            announcement_number=1,
            announcement_text="GitHub issue"
        ), announcements)
