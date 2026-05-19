"""
Test the settings
"""

# Django
from django.test import override_settings

# AA Fleet Finder
from fleetfinder.app_settings import debug_enabled
from fleetfinder.tests import BaseTestCase


class TestSettings(BaseTestCase):
    """
    Test the settings
    """

    @override_settings(DEBUG=True)
    def test_debug_enabled_with_debug_true(self) -> None:
        """
        Test debug_enabled with DEBUG = True

        :return:
        :rtype:
        """

        self.assertTrue(debug_enabled())

    @override_settings(DEBUG=False)
    def test_debug_enabled_with_debug_false(self) -> None:
        """
        Test debug_enabled with DEBUG = False

        :return:
        :rtype:
        """

        self.assertFalse(debug_enabled())
