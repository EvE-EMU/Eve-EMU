"""
Test the views for the Fleet Finder application.
"""

# Standard Library
import datetime
import json
from http import HTTPStatus
from types import SimpleNamespace
from unittest.mock import MagicMock, Mock, patch

# Django
from django.contrib.auth.models import Group
from django.urls import reverse
from django.utils.timezone import now

# Alliance Auth
from allianceauth.groupmanagement.models import AuthGroup
from esi.exceptions import HTTPClientError

# AA Fleet Finder
from fleetfinder.models import Fleet
from fleetfinder.tests import BaseTestCase
from fleetfinder.tests.utils import create_fake_user
from fleetfinder.views import (
    _get_and_validate_fleet,
    ajax_fleet_kick_member,
    create_fleet,
    join_fleet,
    save_fleet,
)


def _dt_to_iso(dt: datetime.datetime) -> str:
    """
    Helper :: Convert a datetime object to ISO 8601 format.

    @see https://github.com/django/django/blob/main/django/core/serializers/json.py#L92-L98

    :param dt:
    :type dt:
    :return:
    :rtype:
    """

    r = dt.isoformat()

    if dt.microsecond:
        r = r[:23] + r[26:]

    if r.endswith("+00:00"):
        r = r.removesuffix("+00:00") + "Z"

    return r


class FleetfinderTestViews(BaseTestCase):
    """
    Base test case for Fleet Finder views.
    This class sets up the necessary users and fleet ID for testing.
    It includes a user with the `fleetfinder.manage_fleets` permission
    and a user with `fleetfinder.access_fleetfinder` access permissions.
    The fleet ID is set to a predefined value for testing purposes.
    """

    @classmethod
    def setUp(cls):
        """
        Set up the test case.

        :return:
        :rtype:
        """

        cls.user_with_manage_perms = create_fake_user(
            character_id=1000,
            character_name="Jean Luc Picard",
            permissions=["fleetfinder.access_fleetfinder", "fleetfinder.manage_fleets"],
        )
        cls.user_with_basic_acces_perms = create_fake_user(
            character_id=1001,
            character_name="William Riker",
            permissions=["fleetfinder.access_fleetfinder"],
        )

        cls.fleet_created_at = now()

        cls.fleet = Fleet(
            fleet_id=12345,
            name="Starfleet",
            fleet_commander=cls.user_with_manage_perms.profile.main_character,
            created_at=cls.fleet_created_at,
            is_free_move=False,
        )
        cls.fleet.save()

        cls.fleet_id = 12345


class TestHelperGetAndValidateFleet(FleetfinderTestViews):
    """
    Tests for the _get_and_validate_fleet helper function.
    """

    def test_retrieves_fleet_information_successfully(self):
        """
        Test that the _get_and_validate_fleet function retrieves fleet information successfully.

        :return:
        :rtype:
        """

        mock_token = MagicMock(character_id=12345)
        mock_fleet_result = MagicMock(fleet_id=67890, fleet_boss_id=12345)
        esi_stub = SimpleNamespace(
            client=SimpleNamespace(
                Fleets=SimpleNamespace(GetCharactersCharacterIdFleet=MagicMock())
            )
        )

        with patch("fleetfinder.views.esi", new=esi_stub):
            esi_stub.client.Fleets.GetCharactersCharacterIdFleet.return_value.result.return_value = (
                mock_fleet_result
            )
            result = _get_and_validate_fleet(mock_token, 12345)

        self.assertEqual(result, mock_fleet_result)

    def test_raises_value_error_when_fleet_not_found(self):
        """
        Test that the _get_and_validate_fleet function raises a ValueError when fleet is not found.

        :return:
        :rtype:
        """

        mock_token = MagicMock(character_id=12345)
        esi_stub = SimpleNamespace(
            client=SimpleNamespace(
                Fleets=SimpleNamespace(GetCharactersCharacterIdFleet=MagicMock())
            )
        )

        with patch("fleetfinder.views.esi", new=esi_stub):
            esi_stub.client.Fleets.GetCharactersCharacterIdFleet.side_effect = (
                HTTPClientError(404, {}, {})
            )

            with self.assertRaises(ValueError) as context:
                _get_and_validate_fleet(mock_token, 12345)

        self.assertEqual(str(context.exception), "Fleet not found")

    def test_raises_runtime_error_on_unexpected_exception(self):
        """
        Test that the _get_and_validate_fleet function raises a RuntimeError on unexpected exceptions.

        :return:
        :rtype:
        """

        mock_token = MagicMock(character_id=12345)
        esi_stub = SimpleNamespace(
            client=SimpleNamespace(
                Fleets=SimpleNamespace(GetCharactersCharacterIdFleet=MagicMock())
            )
        )

        with patch("fleetfinder.views.esi", new=esi_stub):
            esi_stub.client.Fleets.GetCharactersCharacterIdFleet.side_effect = (
                Exception("Unexpected error")
            )

            with self.assertRaises(RuntimeError) as context:
                _get_and_validate_fleet(mock_token, 12345)

        self.assertIn("Error retrieving fleet from ESI", str(context.exception))

    def test_raises_value_error_when_fleet_id_is_missing(self):
        """
        Test that the _get_and_validate_fleet function raises a ValueError when fleet ID is missing.

        :return:
        :rtype:
        """

        mock_token = MagicMock(character_id=12345)
        mock_fleet_result = MagicMock(fleet_id=None)
        esi_stub = SimpleNamespace(
            client=SimpleNamespace(
                Fleets=SimpleNamespace(GetCharactersCharacterIdFleet=MagicMock())
            )
        )
        with patch("fleetfinder.views.esi", new=esi_stub):
            esi_stub.client.Fleets.GetCharactersCharacterIdFleet.return_value.result.return_value = (
                mock_fleet_result
            )
            with patch(
                "fleetfinder.views.EveCharacter.objects.get"
            ) as mock_get_character:
                mock_get_character.return_value.character_name = "Commander"
                with self.assertRaises(ValueError) as context:
                    _get_and_validate_fleet(mock_token, 12345)
        self.assertIn("No fleet found for Commander", str(context.exception))

    def test_raises_value_error_when_not_fleet_boss(self):
        """
        Test that the _get_and_validate_fleet function raises a ValueError when the user is not the fleet boss.

        :return:
        :rtype:
        """

        mock_token = MagicMock(character_id=12345)
        mock_fleet_result = MagicMock(fleet_id=67890, fleet_boss_id=54321)

        esi_stub = SimpleNamespace(
            client=SimpleNamespace(
                Fleets=SimpleNamespace(GetCharactersCharacterIdFleet=MagicMock())
            )
        )

        with patch("fleetfinder.views.esi", new=esi_stub):
            esi_stub.client.Fleets.GetCharactersCharacterIdFleet.return_value.result.return_value = (
                mock_fleet_result
            )

            with patch(
                "fleetfinder.views.EveCharacter.objects.get"
            ) as mock_get_character:
                mock_get_character.return_value.character_name = "Commander"

                with self.assertRaises(ValueError) as context:
                    _get_and_validate_fleet(mock_token, 12345)

        self.assertIn("Commander is not the fleet boss", str(context.exception))


class TestAjaxDashboardView(FleetfinderTestViews):
    """
    Test the ajax_dashboard view in the Fleet Finder application.
    This view is responsible for rendering the dashboard with fleet data.
    It should return a JSON response containing fleet information,
    including fleet names, commanders, and group associations.
    If no fleets are available, it should return an empty list.
    It should also filter fleets based on the user's groups.
    """

    @patch("fleetfinder.views.get_all_characters_from_user")
    def test_renders_dashboard_with_fleet_data_with_basic_access(
        self, mock_get_characters
    ):
        """
        Test that the ajax_dashboard view renders the dashboard with fleet data
        when the user has basic access permissions.

        :param mock_get_characters:
        :type mock_get_characters:
        :return:
        :rtype:
        """

        mock_get_characters.return_value = [
            self.user_with_manage_perms.profile.main_character
        ]

        fleet = self.fleet
        fleet.groups.set([])

        self.client.force_login(self.user_with_basic_acces_perms)
        url = reverse("fleetfinder:ajax_dashboard")
        join_url = reverse("fleetfinder:join_fleet", args=[self.fleet_id])
        response = self.client.get(url)

        expected_response = [
            {
                "fleet_commander": {
                    "html": '<img class="rounded eve-character-portrait" src="https://images.evetech.net/characters/1000/portrait?size=32" alt="Jean Luc Picard" loading="lazy">Jean Luc Picard',
                    "sort": "Jean Luc Picard",
                },
                "fleet_name": "Starfleet",
                "created_at": _dt_to_iso(self.fleet_created_at),
                "actions": f'<a href="{join_url}" class="btn btn-sm btn-success ms-1" data-bs-tooltip="aa-fleetfinder" title="Join fleet"><i class="fa-solid fa-right-to-bracket"></i></a>',
            }
        ]

        self.assertEqual(response.status_code, HTTPStatus.OK)
        self.assertIn("Starfleet", response.json()[0]["fleet_name"])
        self.assertIn("Jean Luc Picard", response.json()[0]["fleet_commander"]["html"])
        self.assertEqual(response.json(), expected_response)

    @patch("fleetfinder.views.get_all_characters_from_user")
    def test_renders_dashboard_with_fleet_data_with_manage_access(
        self, mock_get_characters
    ):
        """
        Test that the ajax_dashboard view renders the dashboard with fleet data
        when the user has manage access permissions.

        :param mock_get_characters:
        :type mock_get_characters:
        :return:
        :rtype:
        """

        mock_get_characters.return_value = [
            self.user_with_manage_perms.profile.main_character
        ]

        fleet = self.fleet
        fleet.groups.set([])

        self.client.force_login(self.user_with_manage_perms)
        url = reverse("fleetfinder:ajax_dashboard")
        join_url = reverse("fleetfinder:join_fleet", args=[self.fleet_id])
        details_url = reverse("fleetfinder:fleet_details", args=[self.fleet_id])
        edit_url = reverse("fleetfinder:edit_fleet", args=[self.fleet_id])
        response = self.client.get(url)

        expected_response = [
            {
                "fleet_commander": {
                    "html": '<img class="rounded eve-character-portrait" src="https://images.evetech.net/characters/1000/portrait?size=32" alt="Jean Luc Picard" loading="lazy">Jean Luc Picard',
                    "sort": "Jean Luc Picard",
                },
                "fleet_name": "Starfleet",
                "created_at": _dt_to_iso(self.fleet_created_at),
                "actions": (
                    f'<a href="{join_url}" class="btn btn-sm btn-success ms-1" data-bs-tooltip="aa-fleetfinder" title="Join fleet"><i class="fa-solid fa-right-to-bracket"></i></a>'
                    f'<a href="{details_url}" class="btn btn-sm btn-info ms-1" data-bs-tooltip="aa-fleetfinder" title="View fleet details"><i class="fa-solid fa-eye"></i></a>'
                    f'<a href="{edit_url}" class="btn btn-sm btn-warning ms-1" data-bs-tooltip="aa-fleetfinder" title="Edit fleet advert"><i class="fa-solid fa-pen-to-square"></i></a>'
                ),
            }
        ]

        self.assertEqual(response.status_code, HTTPStatus.OK)
        self.assertIn("Starfleet", response.json()[0]["fleet_name"])
        self.assertIn("Jean Luc Picard", response.json()[0]["fleet_commander"]["html"])
        self.assertEqual(response.json(), expected_response)

    @patch("fleetfinder.views.get_all_characters_from_user")
    def test_returns_empty_data_when_no_fleets_available(self, mock_get_characters):
        """
        Test that the ajax_dashboard view returns an empty list when no fleets are available.

        :param mock_get_characters:
        :type mock_get_characters:
        :return:
        :rtype:
        """

        mock_get_characters.return_value = [
            self.user_with_manage_perms.profile.main_character
        ]

        Fleet.objects.all().delete()  # Remove all fleets

        self.client.force_login(self.user_with_basic_acces_perms)
        url = reverse("fleetfinder:ajax_dashboard")
        response = self.client.get(url)

        self.assertEqual(response.status_code, HTTPStatus.OK)
        self.assertEqual(response.json(), [])

    @patch("fleetfinder.views.get_all_characters_from_user")
    def test_filters_fleets_by_user_groups(self, mock_get_characters):
        """
        Test that the ajax_dashboard view filters fleets based on the user's groups.

        :param mock_get_characters:
        :type mock_get_characters:
        :return:
        :rtype:
        """

        mock_get_characters.return_value = [
            self.user_with_manage_perms.profile.main_character
        ]

        group_obj = Group.objects.create(name="Starfleet Officers")
        auth_group, _ = AuthGroup.objects.get_or_create(group=group_obj)
        fleet = self.fleet
        fleet.groups.set([auth_group])

        self.client.force_login(self.user_with_basic_acces_perms)
        self.user_with_basic_acces_perms.groups.add(group_obj)
        url = reverse("fleetfinder:ajax_dashboard")
        response = self.client.get(url)

        self.assertEqual(response.status_code, HTTPStatus.OK)
        self.assertIn("Starfleet", response.json()[0]["fleet_name"])


class TestCreateFleetView(FleetfinderTestViews):
    """
    Test the create_fleet view in the Fleet Finder application.
    This view is responsible for creating new fleet adverts.
    """

    def test_redirects_to_dashboard_when_token_validation_fails(self):
        """
        Test that the create_fleet view redirects to the dashboard when token validation fails.

        :return:
        :rtype:
        """

        mock_request = MagicMock(method="POST", user=MagicMock())
        mock_request.session = MagicMock(
            session_key="session123", exists=MagicMock(return_value=True)
        )
        mock_token = MagicMock(character_id=12345)

        with patch("fleetfinder.views._get_and_validate_fleet") as mock_validate_fleet:
            mock_validate_fleet.side_effect = ValueError("Invalid token")
            view_func = create_fleet

            while hasattr(view_func, "__wrapped__"):
                view_func = view_func.__wrapped__

            response = view_func(mock_request, mock_token)

        self.assertEqual(response.status_code, HTTPStatus.FOUND)
        self.assertEqual(response.url, reverse("fleetfinder:dashboard"))

    def test_redirects_to_dashboard_on_get_request(self):
        """
        Test that the create_fleet view redirects to the dashboard on a GET request.

        :return:
        :rtype:
        """

        mock_request = MagicMock(method="GET", user=self.user_with_manage_perms)
        mock_request.session = MagicMock(
            session_key="session123", exists=MagicMock(return_value=True)
        )
        mock_token = MagicMock(character_id=12345)
        with (
            patch("fleetfinder.views._get_and_validate_fleet") as mock_validate_fleet,
            patch("fleetfinder.views.AuthGroup.objects.filter") as mock_filter,
        ):
            mock_validate_fleet.return_value = MagicMock()
            mock_filter.return_value = []
            view_func = create_fleet
            while hasattr(view_func, "__wrapped__"):
                view_func = view_func.__wrapped__
            response = view_func(mock_request, mock_token)
        self.assertEqual(response.status_code, HTTPStatus.FOUND)
        self.assertEqual(response.url, reverse("fleetfinder:dashboard"))

    def test_renders_create_fleet_template_on_valid_post_request(self):
        """
        Test that the create_fleet view renders the create fleet template on a valid POST request.

        :return:
        :rtype:
        """
        mock_request = MagicMock(method="POST", user=MagicMock())
        mock_request.session = MagicMock(
            session_key="session123", exists=MagicMock(return_value=True)
        )
        mock_token = MagicMock(character_id=12345)
        with (
            patch("fleetfinder.views._get_and_validate_fleet") as mock_validate_fleet,
            patch("fleetfinder.views.AuthGroup.objects.filter") as mock_filter,
            patch("fleetfinder.views.render") as mock_render,
        ):
            mock_validate_fleet.return_value = MagicMock()
            mock_filter.return_value = []
            view_func = create_fleet
            while hasattr(view_func, "__wrapped__"):
                view_func = view_func.__wrapped__
            view_func(mock_request, mock_token)
            mock_render.assert_called_once_with(
                request=mock_request,
                template_name="fleetfinder/create-fleet.html",
                context={"character_id": mock_token.character_id, "auth_groups": []},
            )


class TestJoinFleetView(FleetfinderTestViews):
    """
    Test the join_fleet view in the Fleet Finder application.
    This view is responsible for allowing users to join a fleet.
    It should redirect to the fleet details page after joining.
    If the fleet does not exist, it should return a 404 status code.
    """

    def test_redirects_to_dashboard_if_fleet_not_found(self):
        """
        Test that the join_fleet view redirects to the dashboard if the fleet is not found.

        :return:
        :rtype:
        """

        mock_request = MagicMock(method="GET", user=MagicMock())
        mock_request.user.groups.all.return_value = []

        with patch("fleetfinder.views.Fleet.objects.filter") as mock_filter:
            mock_filter.return_value.count.return_value = 0
            response = join_fleet(mock_request, fleet_id=1)

        self.assertEqual(response.status_code, HTTPStatus.FOUND)
        self.assertEqual(response.url, reverse("fleetfinder:dashboard"))

    def test_redirects_to_dashboard_on_post_and_sends_invitations(self):
        """
        Test that the join_fleet view redirects to the dashboard on a POST request and sends fleet invitations.

        :return:
        :rtype:
        """

        mock_request = MagicMock(method="POST", user=MagicMock())
        mock_request.user.groups.all.return_value = []
        mock_request.POST.getlist.return_value = [1001, 1002]

        with (
            patch("fleetfinder.views.Fleet.objects.filter") as mock_filter,
            patch(
                "fleetfinder.views.send_fleet_invitation.delay"
            ) as mock_send_invitation,
        ):
            mock_filter.return_value.count.return_value = 1
            response = join_fleet(mock_request, fleet_id=1)

            mock_send_invitation.assert_called_once_with(
                character_ids=[1001, 1002], fleet_id=1
            )

        self.assertEqual(response.status_code, HTTPStatus.FOUND)
        self.assertEqual(response.url, reverse("fleetfinder:dashboard"))

    def test_renders_join_fleet_template_with_characters_on_get(self):
        """
        Test that the join_fleet view renders the join fleet template with characters on a GET request.

        :return:
        :rtype:
        """

        mock_request = MagicMock(method="GET", user=MagicMock())
        mock_request.user.groups.all.return_value = []
        mock_request.user.__str__.return_value = "test_user"
        mock_characters = [
            MagicMock(character_name="Char1"),
            MagicMock(character_name="Char2"),
        ]

        with (
            patch("fleetfinder.views.Fleet.objects.filter") as mock_filter,
            patch(
                "fleetfinder.views.EveCharacter.objects.filter"
            ) as mock_character_filter,
            patch("fleetfinder.views.render") as mock_render,
        ):
            mock_filter.return_value.count.return_value = 1
            mock_character_filter.return_value.select_related.return_value.order_by.return_value = (
                mock_characters
            )

            join_fleet(mock_request, fleet_id=1)

            mock_render.assert_called_once_with(
                request=mock_request,
                template_name="fleetfinder/join-fleet.html",
                context={"characters": mock_characters},
            )


class TestSaveFleetView(FleetfinderTestViews):
    """
    Test the save_fleet view in the Fleet Finder application.
    This view is responsible for saving fleet details.
    It should redirect to the dashboard after saving.
    """

    def test_redirects_to_dashboard_if_request_method_is_not_post(self):
        """
        Test that the save_fleet view redirects to the dashboard if the request method is not POST.

        :return:
        :rtype:
        """

        mock_request = MagicMock(method="GET", user=MagicMock())
        response = save_fleet(mock_request)

        self.assertEqual(response.status_code, HTTPStatus.FOUND)
        self.assertEqual(response.url, reverse("fleetfinder:dashboard"))

    def test_creates_new_fleet_with_valid_data(self):
        """
        Test that the save_fleet view creates a new fleet with valid data.

        :return:
        :rtype:
        """

        mock_request = MagicMock(method="POST", user=MagicMock())
        post_data = {
            "character_id": "12345",
            "free_move": "on",
            "name": "Test Fleet",
            "groups": ["1", "2"],
        }
        mock_request.POST = MagicMock()
        mock_request.POST.get.side_effect = lambda k, default=None: post_data.get(
            k, default
        )
        mock_request.POST.getlist.side_effect = lambda k, default=None: post_data.get(
            k, default
        )

        esi_stub = SimpleNamespace(
            client=SimpleNamespace(Fleets=SimpleNamespace(PutFleetsFleetId=MagicMock()))
        )

        with (
            patch(
                "fleetfinder.views.Fleet.objects.get_or_create"
            ) as mock_get_or_create,
            patch("fleetfinder.views.Token.get_token") as mock_get_token,
            patch("fleetfinder.views._get_and_validate_fleet") as mock_validate_fleet,
            patch("fleetfinder.views.EveCharacter.objects.get") as mock_eve_get,
            patch("fleetfinder.views.esi", new=esi_stub),
        ):
            mock_get_or_create.return_value = (MagicMock(), True)
            mock_get_token.return_value = MagicMock()
            mock_validate_fleet.return_value = MagicMock(fleet_id=1)
            mock_eve_get.return_value = MagicMock(
                character_id=int(post_data["character_id"])
            )
            response = save_fleet(mock_request)

        self.assertEqual(response.status_code, HTTPStatus.FOUND)
        self.assertEqual(response.url, reverse("fleetfinder:dashboard"))

    def test_updates_existing_fleet_with_valid_data(self):
        """
        Test that the save_fleet view updates an existing fleet with valid data.

        :return:
        :rtype:
        """

        mock_request = MagicMock(method="POST", user=MagicMock())
        post_data = {
            "character_id": "12345",
            "free_move": "on",
            "name": "Updated Fleet",
            "groups": ["1", "2"],
        }
        mock_request.POST = MagicMock()
        mock_request.POST.get.side_effect = lambda k, default=None: post_data.get(
            k, default
        )
        mock_request.POST.getlist.side_effect = lambda k, default=None: post_data.get(
            k, default
        )

        mock_fleet = MagicMock()
        esi_stub = SimpleNamespace(
            client=SimpleNamespace(Fleets=SimpleNamespace(PutFleetsFleetId=MagicMock()))
        )

        with (
            patch(
                "fleetfinder.views.Fleet.objects.get_or_create"
            ) as mock_get_or_create,
            patch("fleetfinder.views.Token.get_token") as mock_get_token,
            patch("fleetfinder.views._get_and_validate_fleet") as mock_validate_fleet,
            patch("fleetfinder.views.EveCharacter.objects.get") as mock_eve_get,
            patch("fleetfinder.views.esi", new=esi_stub),
        ):
            mock_get_or_create.return_value = (mock_fleet, False)
            mock_get_token.return_value = MagicMock()
            mock_validate_fleet.return_value = MagicMock(fleet_id=1)
            mock_eve_get.return_value = MagicMock(
                character_id=int(post_data["character_id"])
            )
            response = save_fleet(mock_request)
            mock_fleet.save.assert_called_once()

        self.assertEqual(response.status_code, HTTPStatus.FOUND)
        self.assertEqual(response.url, reverse("fleetfinder:dashboard"))

    def test_handles_http_client_error_during_fleet_creation(self):
        """
        Test that the save_fleet view handles HTTPClientError during fleet creation.

        :return:
        :rtype:
        """

        mock_request = MagicMock(method="POST", user=MagicMock())
        post_data = {
            "character_id": "12345",
            "free_move": "on",
            "name": "Test Fleet",
            "groups": ["1", "2"],
        }
        mock_request.POST = MagicMock()
        mock_request.POST.get.side_effect = lambda k, default=None: post_data.get(
            k, default
        )
        mock_request.POST.getlist.side_effect = lambda k, default=None: post_data.get(
            k, default
        )

        esi_stub = SimpleNamespace(
            client=SimpleNamespace(Fleets=SimpleNamespace(PutFleetsFleetId=MagicMock()))
        )

        with (
            patch("fleetfinder.views.Token.get_token") as mock_get_token,
            patch("fleetfinder.views._get_and_validate_fleet") as mock_validate_fleet,
            patch("fleetfinder.views.messages.error") as mock_messages,
            patch("fleetfinder.views.EveCharacter.objects.get") as mock_eve_get,
            patch("fleetfinder.views.esi", new=esi_stub),
        ):
            mock_get_token.return_value = MagicMock()
            mock_validate_fleet.side_effect = HTTPClientError(400, {}, {})
            mock_eve_get.return_value = MagicMock(
                character_id=int(post_data["character_id"])
            )
            response = save_fleet(mock_request)
            mock_messages.assert_called_once()

        self.assertEqual(response.status_code, HTTPStatus.FOUND)
        self.assertEqual(response.url, reverse("fleetfinder:dashboard"))

    def test_handles_value_error_during_fleet_creation(self):
        """
        Test that the save_fleet view handles ValueError during fleet creation.

        :return:
        :rtype:
        """

        mock_request = MagicMock(method="POST", user=MagicMock())
        post_data = {
            "character_id": "12345",
            "free_move": "on",
            "name": "Test Fleet",
            "groups": ["1", "2"],
        }
        mock_request.POST = MagicMock()
        mock_request.POST.get.side_effect = lambda k, default=None: post_data.get(
            k, default
        )
        mock_request.POST.getlist.side_effect = lambda k, default=None: post_data.get(
            k, default
        )

        esi_stub = SimpleNamespace(
            client=SimpleNamespace(Fleets=SimpleNamespace(PutFleetsFleetId=MagicMock()))
        )

        with (
            patch("fleetfinder.views.Token.get_token") as mock_get_token,
            patch("fleetfinder.views._get_and_validate_fleet") as mock_validate_fleet,
            patch("fleetfinder.views.messages.error") as mock_messages,
            patch("fleetfinder.views.EveCharacter.objects.get") as mock_eve_get,
            patch("fleetfinder.views.esi", new=esi_stub),
        ):
            mock_get_token.return_value = MagicMock()
            mock_validate_fleet.side_effect = ValueError("Invalid fleet")
            mock_eve_get.return_value = MagicMock(
                character_id=int(post_data["character_id"])
            )
            response = save_fleet(mock_request)
            mock_messages.assert_called_once()

        self.assertEqual(response.status_code, HTTPStatus.FOUND)
        self.assertEqual(response.url, reverse("fleetfinder:dashboard"))


class TestFleetEditView(FleetfinderTestViews):
    """
    Test the edit_fleet view in the Fleet Finder application.
    This view is responsible for editing fleet details.
    """

    @patch("fleetfinder.views.Fleet.objects.get")
    @patch("fleetfinder.views.AuthGroup.objects.filter")
    def test_renders_edit_fleet_template_with_correct_context(
        self, mock_filter_groups, mock_get_fleet
    ):
        """
        Test that the edit_fleet view renders the correct template and context.

        :param mock_filter_groups:
        :type mock_filter_groups:
        :param mock_get_fleet:
        :type mock_get_fleet:
        :return:
        :rtype:
        """

        mock_get_fleet.return_value = self.fleet
        group1 = Mock(spec=AuthGroup)
        group1.name = "Group1"
        group2 = Mock(spec=AuthGroup)
        group2.name = "Group2"
        mock_filter_groups.return_value = [group1, group2]

        self.client.force_login(self.user_with_manage_perms)
        url = reverse("fleetfinder:edit_fleet", args=[self.fleet_id])
        response = self.client.get(url)

        self.assertTemplateUsed(response, "fleetfinder/edit-fleet.html")
        self.assertEqual(response.context["fleet"].name, "Starfleet")
        self.assertEqual(response.context["character_id"], 1000)
        self.assertEqual(len(response.context["auth_groups"]), 2)

    @patch("fleetfinder.views.Fleet.objects.get")
    def test_redirects_to_dashboard_if_fleet_does_not_exist(self, mock_get_fleet):
        """
        Test that the edit_fleet view redirects to the dashboard if the fleet does not exist.

        :param mock_get_fleet:
        :type mock_get_fleet:
        :return:
        :rtype:
        """

        mock_get_fleet.side_effect = Fleet.DoesNotExist

        self.client.force_login(self.user_with_manage_perms)
        url = reverse("fleetfinder:edit_fleet", args=[99999])
        response = self.client.get(url)

        self.assertEqual(response.status_code, HTTPStatus.FOUND)
        self.assertRedirects(response, reverse("fleetfinder:dashboard"))


class TestFleetDetailsView(FleetfinderTestViews):
    """
    Test the fleet_details view in the Fleet Finder application.
    This view is responsible for rendering the fleet details page.
    It should render the correct template and require the user to have
    the 'fleetfinder.manage_fleets' permission to access it.
    If the fleet does not exist, it should return a 404 status code.
    """

    @patch("fleetfinder.views.Fleet.objects.get")
    def test_fleet_details_renders_correct_template(self, mock_get_fleet):
        """
        Test that the fleet_details view renders the correct template.

        :param mock_get_fleet:
        :type mock_get_fleet:
        :return:
        :rtype:
        """

        mock_get_fleet.return_value = Fleet(fleet_id=self.fleet_id)

        self.client.force_login(self.user_with_manage_perms)
        url = reverse("fleetfinder:fleet_details", args=[self.fleet_id])
        response = self.client.get(url)

        self.assertEqual(response.status_code, HTTPStatus.OK)
        self.assertTemplateUsed(response, "fleetfinder/fleet-details.html")

    @patch("fleetfinder.views.Fleet.objects.get")
    def test_fleet_details_requires_manage_permission(self, mock_get_fleet):
        """
        Test that the fleet_details view requires the user to have the 'fleetfinder.manage_fleets' permission.

        :param mock_get_fleet:
        :type mock_get_fleet:
        :return:
        :rtype:
        """

        mock_get_fleet.return_value = Fleet(fleet_id=self.fleet_id)

        self.client.force_login(self.user_with_basic_acces_perms)
        url = reverse("fleetfinder:fleet_details", args=[self.fleet_id])
        response = self.client.get(url)

        self.assertEqual(response.status_code, HTTPStatus.FOUND)

    def test_fleet_redirects_to_dashboard_if_not_found(self):
        """
        Test that the fleet_details view redirects to the dashboard if the fleet does not exist.

        :return:
        :rtype:
        """

        self.client.force_login(self.user_with_manage_perms)

        response = self.client.get(reverse("fleetfinder:fleet_details", args=[123]))

        self.assertEqual(response.status_code, HTTPStatus.FOUND)
        self.assertEqual(response.url, reverse("fleetfinder:dashboard"))


class TestAjaxFleetDetailsView(FleetfinderTestViews):
    """
    Test the ajax_fleet_details view in the Fleet Finder application.
    This view is responsible for returning fleet details in JSON format.
    It should return the fleet members and their ship types, or an empty list if the fleet is empty.
    """

    @patch("fleetfinder.views.get_fleet_composition")
    def test_returns_correct_fleet_details(self, mock_get_fleet_composition):
        """
        Test that the ajax_fleet_details view returns the correct fleet details.

        :param mock_get_fleet_composition:
        :type mock_get_fleet_composition:
        :return:
        :rtype:
        """

        mock_get_fleet_composition.return_value = SimpleNamespace(
            fleet=[{"name": "Pilot1"}, {"name": "Pilot2"}, {"name": "Pilot3"}],
            aggregate={"Frigate": 2, "Cruiser": 1},
        )

        self.client.force_login(user=self.user_with_manage_perms)

        url = reverse("fleetfinder:ajax_fleet_details", args=[self.fleet_id])
        response = self.client.get(url)

        expected_fleet_composition = {
            "fleet_member": [
                {"name": "Pilot1"},
                {"name": "Pilot2"},
                {"name": "Pilot3"},
            ],
            "fleet_composition": [
                {"ship_type_name": "Frigate", "number": 2},
                {"ship_type_name": "Cruiser", "number": 1},
            ],
        }

        self.assertEqual(response.status_code, HTTPStatus.OK)
        self.assertEqual(json.loads(response.content), expected_fleet_composition)

    @patch("fleetfinder.views.get_fleet_composition")
    def test_handles_empty_fleet(self, mock_get_fleet_composition):
        """
        Test that the ajax_fleet_details view handles an empty fleet correctly.

        :param mock_get_fleet_composition:
        :type mock_get_fleet_composition:
        :return:
        :rtype:
        """

        mock_get_fleet_composition.return_value = SimpleNamespace(
            fleet=[],
            aggregate={},
        )

        self.client.force_login(user=self.user_with_manage_perms)

        url = reverse("fleetfinder:ajax_fleet_details", args=[self.fleet_id])
        response = self.client.get(url)

        expected_fleet_composition = {"fleet_member": [], "fleet_composition": []}

        self.assertEqual(response.status_code, HTTPStatus.OK)
        self.assertEqual(json.loads(response.content), expected_fleet_composition)

    @patch("fleetfinder.views.get_fleet_composition")
    def test_returns_error_when_fleet_does_not_exist(self, mock_get_fleet_composition):
        """
        Test that the ajax_fleet_details view returns an error when the fleet does not exist.

        :param mock_get_fleet_composition:
        :type mock_get_fleet_composition:
        :return:
        :rtype:
        """

        mock_get_fleet_composition.side_effect = Fleet.DoesNotExist

        self.client.force_login(user=self.user_with_manage_perms)

        url = reverse("fleetfinder:ajax_fleet_details", args=[123])
        response = self.client.get(url)

        self.assertEqual(response.status_code, HTTPStatus.OK)
        self.assertJSONEqual(
            response.content,
            {"error": "Fleet with ID 123 does not exist."},
        )

    @patch("fleetfinder.views.get_fleet_composition")
    def test_returns_error_when_runtime_error_occurs(self, mock_get_fleet_composition):
        """
        Test that the ajax_fleet_details view returns an error when a runtime error occurs.

        :param mock_get_fleet_composition:
        :type mock_get_fleet_composition:
        :return:
        :rtype:
        """

        mock_get_fleet_composition.side_effect = RuntimeError("Unexpected error")

        self.client.force_login(user=self.user_with_manage_perms)

        url = reverse("fleetfinder:ajax_fleet_details", args=[123])
        response = self.client.get(url)

        self.assertEqual(response.status_code, HTTPStatus.OK)
        self.assertJSONEqual(
            response.content,
            {"error": "Error retrieving fleet composition: Unexpected error"},
        )


class TestAjaxFleetKickMemberView(FleetfinderTestViews):
    """
    Test the ajax_fleet_kick_member view in the Fleet Finder application.
    This view is responsible for kicking a member from a fleet.
    It should return a JSON response indicating success or failure.
    """

    def test_returns_405_if_request_method_is_not_post(self):
        """
        Test that the ajax_fleet_kick_member view returns a 405 status code if the request method is not POST.

        :return:
        :rtype:
        """

        mock_request = MagicMock(method="GET", user=MagicMock())
        response = ajax_fleet_kick_member(mock_request, fleet_id=1)

        self.assertEqual(response.status_code, HTTPStatus.METHOD_NOT_ALLOWED)
        self.assertEqual(
            json.loads(response.content),
            {"success": False, "error": "Method not allowed"},
        )

    def test_returns_404_if_fleet_does_not_exist(self):
        """
        Test that the ajax_fleet_kick_member view returns a 404 status code if the fleet does not exist.

        :return:
        :rtype:
        """

        mock_request = MagicMock(method="POST", body=json.dumps({"memberId": 123}))

        with patch(
            "fleetfinder.views.Fleet.objects.get", side_effect=Fleet.DoesNotExist
        ):
            response = ajax_fleet_kick_member(mock_request, fleet_id=1)

        self.assertEqual(response.status_code, HTTPStatus.NOT_FOUND)
        self.assertEqual(
            json.loads(response.content), {"success": False, "error": "Fleet not found"}
        )

    def test_returns_400_if_member_id_is_missing(self):
        """
        Test that the ajax_fleet_kick_member view returns a 400 status code if the member ID is missing.

        :return:
        :rtype:
        """

        mock_request = MagicMock(method="POST", body=json.dumps({}))

        with patch("fleetfinder.views.Fleet.objects.get") as mock_get:
            mock_get.return_value = MagicMock()
            response = ajax_fleet_kick_member(mock_request, fleet_id=1)

        self.assertEqual(response.status_code, HTTPStatus.BAD_REQUEST)
        self.assertEqual(
            json.loads(response.content),
            {"success": False, "error": "Member ID required"},
        )

    def test_returns_400_if_request_body_is_invalid(self):
        """
        Test that the ajax_fleet_kick_member view returns a 400 status code if the request body is invalid.

        :return:
        :rtype:
        """

        mock_request = MagicMock(method="POST", body="invalid_json")

        with patch("fleetfinder.views.Fleet.objects.get") as mock_get:
            mock_get.return_value = MagicMock()
            response = ajax_fleet_kick_member(mock_request, fleet_id=1)

        self.assertEqual(response.status_code, HTTPStatus.BAD_REQUEST)
        self.assertEqual(
            json.loads(response.content),
            {"success": False, "error": "Invalid request data"},
        )

    def test_returns_404_if_member_not_found_in_fleet(self):
        """
        Test that the ajax_fleet_kick_member view returns a 404 status code if the member is not found in the fleet.

        :return:
        :rtype:
        """

        mock_request = MagicMock(method="POST", body=json.dumps({"memberId": 123}))
        esi_stub = SimpleNamespace(
            client=SimpleNamespace(
                Fleets=SimpleNamespace(
                    DeleteFleetsFleetIdMembersMemberId=MagicMock(
                        side_effect=HTTPClientError(404, {}, {})
                    )
                )
            )
        )

        with (
            patch("fleetfinder.views.Fleet.objects.get") as mock_get,
            patch("fleetfinder.views.esi", new=esi_stub),
        ):
            mock_get.return_value = MagicMock(fleet_commander=MagicMock(character_id=1))
            response = ajax_fleet_kick_member(mock_request, fleet_id=1)

        self.assertEqual(response.status_code, HTTPStatus.NOT_FOUND)
        self.assertEqual(
            json.loads(response.content),
            {"success": False, "error": "Member not found in fleet"},
        )

    def test_returns_esi_error_when_unexpected_http_error_occurs(self):
        mock_request = MagicMock(method="POST", body=json.dumps({"memberId": 123}))
        esi_stub = SimpleNamespace(
            client=SimpleNamespace(
                Fleets=SimpleNamespace(
                    DeleteFleetsFleetIdMembersMemberId=MagicMock(
                        side_effect=HTTPClientError(500, {}, {})
                    )
                )
            )
        )
        with (
            patch("fleetfinder.views.Fleet.objects.get") as mock_get,
            patch("fleetfinder.views.esi", new=esi_stub),
        ):
            mock_get.return_value = MagicMock(fleet_commander=MagicMock(character_id=1))
            response = ajax_fleet_kick_member(mock_request, fleet_id=1)
        self.assertEqual(response.status_code, 500)
        self.assertEqual(
            json.loads(response.content),
            {
                "success": False,
                "error": "An ESI error occurred: <HTTPClientError 500 {} {}>",
            },
        )

    def test_successfully_kicks_member_from_fleet(self):
        mock_request = MagicMock(method="POST", body=json.dumps({"memberId": 123}))
        esi_stub = SimpleNamespace(
            client=SimpleNamespace(
                Fleets=SimpleNamespace(
                    DeleteFleetsFleetIdMembersMemberId=MagicMock(
                        return_value=MagicMock()
                    )
                )
            )
        )
        with (
            patch("fleetfinder.views.Fleet.objects.get") as mock_get,
            patch("fleetfinder.views.esi", new=esi_stub),
        ):
            mock_get.return_value = MagicMock(fleet_commander=MagicMock(character_id=1))
            response = ajax_fleet_kick_member(mock_request, fleet_id=1)
        self.assertEqual(response.status_code, HTTPStatus.OK)
        self.assertEqual(json.loads(response.content), {"success": True})
