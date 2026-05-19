"""
Test the apps' template tags
"""

# AA Fleet Finder
from fleetfinder.templatetags.fleetfinder import get_item
from fleetfinder.tests import BaseTestCase


class TestGetItem(BaseTestCase):
    """
    Test the `get_item` template tag
    """

    def test_returns_value_for_existing_key(self):
        """
        Test should return the value for an existing key

        :return:
        :rtype:
        """

        dictionary = {"key1": "value1", "key2": "value2"}
        result = get_item(dictionary, "key1")

        self.assertEqual(result, "value1")

    def test_returns_none_for_non_existing_key(self):
        """
        Test should return None for a non-existing key

        :return:
        :rtype:
        """

        dictionary = {"key1": "value1", "key2": "value2"}
        result = get_item(dictionary, "key3")

        self.assertIsNone(result)

    def test_returns_none_for_empty_dictionary(self):
        """
        Test should return None for an empty dictionary

        :return:
        :rtype:
        """

        dictionary = {}
        result = get_item(dictionary, "key1")

        self.assertIsNone(result)

    def test_returns_none_for_none_dictionary(self):
        """
        Test should return None for a None dictionary

        :return:
        :rtype:
        """

        dictionary = None
        result = get_item(dictionary, "key1")

        self.assertIsNone(result)
