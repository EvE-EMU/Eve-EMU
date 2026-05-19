"""
Test checks for access to fleetfinder
"""

# Standard Library
from http import HTTPStatus

# Django
from django.contrib.auth.models import Group
from django.urls import reverse

# AA Fleet Finder
from fleetfinder.tests import BaseTestCase
from fleetfinder.tests.utils import create_fake_user


class TestAccess(BaseTestCase):
    """
    Testing module access
    """

    @classmethod
    def setUpClass(cls) -> None:
        """
        Set up groups and users
        """

        super().setUpClass()

        cls.group = Group.objects.create(name="Superhero")

        # User cannot access fleetfinder
        cls.user_1001 = create_fake_user(
            character_id=1001, character_name="Peter Parker"
        )

        # User can access fleetfinder
        cls.user_1002 = create_fake_user(
            character_id=1002,
            character_name="Bruce Wayne",
            permissions=["fleetfinder.access_fleetfinder"],
        )

    def test_has_no_access(self):
        """
        Test that a user without access gets a 302

        :return:
        """

        # given
        self.client.force_login(user=self.user_1001)

        # when
        res = self.client.get(path=reverse(viewname="fleetfinder:dashboard"))

        # then
        self.assertEqual(first=res.status_code, second=HTTPStatus.FOUND)

    def test_has_access(self):
        """
        Test that a user with access gets to see it

        :return:
        """

        # given
        self.client.force_login(user=self.user_1002)

        # when
        res = self.client.get(path=reverse(viewname="fleetfinder:dashboard"))

        # then
        self.assertEqual(first=res.status_code, second=HTTPStatus.OK)
