import hashlib
import logging
from dataclasses import dataclass
from enum import Enum
from urllib.parse import quote_plus

import requests

from django.core.cache import cache

from allianceauth.hooks import get_hooks, register

logger = logging.getLogger(__name__)

# timeout for all requests
REQUESTS_TIMEOUT = 5    # 5 seconds
# max pages to be fetched from gitlab
MAX_PAGES = 50
# Cache time
NOTIFICATION_CACHE_TIME = 300  # 5 minutes


@dataclass
class Announcement:
    """
    Dataclass storing all data for an announcement to be sent arround
    """
    application_name: str
    announcement_url: str
    announcement_number: int
    announcement_text: str

    @classmethod
    def build_from_gitlab_issue_dict(cls, application_name: str, gitlab_issue: dict) -> "Announcement":
        """Builds the announcement from the JSON dict of a GitLab issue"""
        return Announcement(application_name, gitlab_issue["web_url"], gitlab_issue["iid"], gitlab_issue["title"])

    @classmethod
    def build_from_github_issue_dict(cls, application_name: str, github_issue: dict) -> "Announcement":
        """Builds the announcement from the JSON dict of a GitHub issue"""
        return Announcement(application_name, github_issue["html_url"], github_issue["number"], github_issue["title"])

    def get_hash(self):
        """Get a hash of the Announcement for comparison"""
        name = f"{self.application_name}.{self.announcement_number}"
        hash_value = hashlib.sha256(name.encode("utf-8")).hexdigest()
        return hash_value


@dataclass
class AppAnnouncementHook:
    """
    A hook for an application to send GitHub/GitLab issues as announcements on the dashboard

    Args:
        - app_name: The name of your application
        - repository_namespace: The namespace of the remote repository of your application source code.
            It should look like `<username>/<application_name>`.
        - repository_kind: Enumeration to determine if your repository is a GitHub or GitLab repository.
        - label: The label applied to issues that should be seen as announcements, case-sensitive.
            Default value: `announcement`
    """
    class Service(Enum):
        """Simple enumeration to determine which api should be called to access issues"""
        GITLAB = "gitlab"
        GITHUB = "github"

    app_name: str
    repository_namespace: str
    repository_kind: Service
    label: str = "announcement"


    def get_announcement_list(self) -> list[Announcement]:
        """
        Checks the application repository to find issues with the `Announcement` tag and return their title and link to
        be displayed.
        """
        logger.debug("Getting announcement list for the app %s", self.app_name)
        match self.repository_kind:
            case AppAnnouncementHook.Service.GITHUB:
                announcement_list = self._get_github_announcement_list()
            case AppAnnouncementHook.Service.GITLAB:
                announcement_list = self._get_gitlab_announcement_list()
            case _:
                announcement_list = []

        logger.debug("Announcements for app %s: %s", self.app_name, announcement_list)
        return announcement_list

    def _get_github_announcement_list(self) -> list[Announcement]:
        """
        Return the issue list for a GitHub repository
        Will filter if the `pull_request` attribute is present
        """
        raw_list = _fetch_list_from_github(
            f"https://api.github.com/repos/{self.repository_namespace}/issues"
            f"?labels={self.label}"
        )
        return [Announcement.build_from_github_issue_dict(self.app_name, github_issue) for github_issue in raw_list]

    def _get_gitlab_announcement_list(self) -> list[Announcement]:
        """Return the issues list for a GitLab repository"""
        raw_list = _fetch_list_from_gitlab(
            f"https://gitlab.com/api/v4/projects/{quote_plus(self.repository_namespace)}/issues"
            f"?labels={self.label}&state=opened")
        return [Announcement.build_from_gitlab_issue_dict(self.app_name, gitlab_issue) for gitlab_issue in raw_list]

@register("app_announcement_hook")
def alliance_auth_announcements_hook():
    return AppAnnouncementHook("AllianceAuth", "allianceauth/allianceauth", AppAnnouncementHook.Service.GITLAB)

def get_all_applications_announcements() -> list[Announcement]:
    """
    Retrieve all known application announcements and returns them
    """
    application_notifications = []

    hooks = [fn() for fn in get_hooks("app_announcement_hook")]
    for hook in hooks:
        logger.debug(hook)
        try:
            application_notifications.extend(cache.get_or_set(
                f"{hook.app_name}_notification_issues",
                hook.get_announcement_list,
                NOTIFICATION_CACHE_TIME,
            ))
        except requests.HTTPError:
            logger.warning("Error when getting %s notifications", hook, exc_info=True)

    logger.debug(application_notifications)
    if application_notifications:
        application_notifications = application_notifications[:10]

    return application_notifications


def _fetch_list_from_gitlab(url: str, max_pages: int = MAX_PAGES) -> list:
    """returns a list from the GitLab API. Supports paging"""
    result = []

    for page in range(1, max_pages + 1):
        try:
            request = requests.get(
                url, params={'page': page}, timeout=REQUESTS_TIMEOUT
            )
            request.raise_for_status()
        except requests.exceptions.RequestException as e:
            error_str = str(e)

            logger.warning(
                f'Unable to fetch from GitLab API. Error: {error_str}',
                exc_info=True,
            )

            return result

        result += request.json()

        if 'x-total-pages' in request.headers:
            try:
                total_pages = int(request.headers['x-total-pages'])
            except ValueError:
                total_pages = None
        else:
            total_pages = None

        if not total_pages or page >= total_pages:
            break

    return result

def _fetch_list_from_github(url: str, max_pages: int = MAX_PAGES) -> list:
    """returns a list from the GitHub API. Supports paging"""

    result = []
    for page in range(1, max_pages+1):
        try:
            request = requests.get(
                url,
                params={'page': page},
                headers={
                    "Accept": "application/vnd.github+json",
                    "X-GitHub-Api-Version": "2022-11-28"
                },
                timeout=REQUESTS_TIMEOUT,
            )
            request.raise_for_status()
        except requests.exceptions.RequestException as e:
            error_str = str(e)

            logger.warning(
                f'Unable to fetch from GitHub API. Error: {error_str}',
                exc_info=True,
            )

            return result

        result += request.json()
        logger.debug(request.json())

        # https://docs.github.com/en/rest/using-the-rest-api/using-pagination-in-the-rest-api?apiVersion=2022-11-28
        # See Example creating a pagination method
        if not ('link' in request.headers and 'rel=\"next\"' in request.headers['link']):
            break

    return result
