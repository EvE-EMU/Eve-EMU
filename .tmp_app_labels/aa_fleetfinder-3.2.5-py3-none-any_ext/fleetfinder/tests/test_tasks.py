"""
Tests for the fleetfinder.tasks module.
"""

# Standard Library
from datetime import timedelta
from unittest.mock import MagicMock, Mock, patch

# Django
from django.utils import timezone

# Alliance Auth
from esi.exceptions import HTTPClientError

# AA Fleet Finder
from fleetfinder.models import Fleet
from fleetfinder.tasks import (
    ESI_ERROR_GRACE_TIME,
    ESI_MAX_ERROR_COUNT,
    FleetViewAggregate,
    _check_for_esi_fleet,
    _close_esi_fleet,
    _esi_fleet_error_handling,
    _fetch_chunk,
    _get_fleet_aggregate,
    _make_name_lookup,
    _process_fleet,
    _send_invitation,
    check_fleet_adverts,
    get_fleet_composition,
    send_fleet_invitation,
)
from fleetfinder.tests import BaseTestCase


class TestFleetViewAggregateClass(BaseTestCase):
    """
    Tests for the FleetViewAggregate class.
    """

    def test_initializes_with_valid_fleet_and_aggregate(self):
        """
        Test that FleetViewAggregate initializes correctly with valid fleet and aggregate data.

        :return:
        :rtype:
        """

        fleet_data = [{"id": 1, "name": "Fleet Member 1"}]
        aggregate_data = {"ship_type": 5}
        aggregate = FleetViewAggregate(fleet=fleet_data, aggregate=aggregate_data)

        self.assertEqual(aggregate.fleet, fleet_data)
        self.assertEqual(aggregate.aggregate, aggregate_data)

    def test_initializes_with_empty_fleet_and_aggregate(self):
        """
        Test that FleetViewAggregate initializes correctly with empty fleet and aggregate data.

        :return:
        :rtype:
        """

        fleet_data = []
        aggregate_data = {}
        aggregate = FleetViewAggregate(fleet=fleet_data, aggregate=aggregate_data)

        self.assertEqual(aggregate.fleet, fleet_data)
        self.assertEqual(aggregate.aggregate, aggregate_data)

    def test_handles_large_fleet_and_aggregate(self):
        """
        Test that FleetViewAggregate handles large fleet and aggregate data.

        :return:
        :rtype:
        """

        fleet_data = [{"id": i, "name": f"Fleet Member {i}"} for i in range(1000)]
        aggregate_data = {"ship_type": 1000}
        aggregate = FleetViewAggregate(fleet=fleet_data, aggregate=aggregate_data)

        self.assertEqual(len(aggregate.fleet), 1000)
        self.assertEqual(aggregate.aggregate, aggregate_data)


class TestHelperSendInvitation(BaseTestCase):
    """
    Tests for the _send_invitation helper function.
    """

    def test_sends_invitation_successfully(self):
        """
        Test that _send_invitation sends an invitation successfully.

        :return:
        :rtype:
        """

        mock_esi_client = MagicMock()
        mock_esi_client.Fleets.PostFleetsFleetIdMembers.return_value.result.return_value = (
            None
        )

        with patch("fleetfinder.tasks.esi", Mock(client=mock_esi_client)):
            _send_invitation(12345, "mock_token", 67890)

        mock_esi_client.Fleets.PostFleetsFleetIdMembers.assert_called_once_with(
            fleet_id=67890,
            token="mock_token",
            body={"character_id": 12345, "role": "squad_member"},
        )

    def test_handles_esi_client_error_gracefully(self):
        """
        Test that _send_invitation handles ESIClientError gracefully.

        :return:
        :rtype:
        """

        mock_esi_client = MagicMock()
        mock_esi_client.Fleets.PostFleetsFleetIdMembers.return_value.result.side_effect = HTTPClientError(
            500, {}, b""
        )

        with patch("fleetfinder.tasks.esi", Mock(client=mock_esi_client)):
            with self.assertRaises(HTTPClientError):
                _send_invitation(12345, "mock_token", 67890)

        mock_esi_client.Fleets.PostFleetsFleetIdMembers.assert_called_once_with(
            fleet_id=67890,
            token="mock_token",
            body={"character_id": 12345, "role": "squad_member"},
        )


class TestHelperCloseEsiFleet(BaseTestCase):
    """
    Tests for the _close_esi_fleet helper function.
    """

    def test_closes_fleet_and_logs_reason(self):
        """
        Test that _close_esi_fleet closes the fleet and logs the reason.

        :return:
        :rtype:
        """

        mock_fleet = MagicMock()

        with patch("fleetfinder.tasks.logger.info") as mock_info:
            _close_esi_fleet(fleet=mock_fleet, reason="Test reason")

        mock_fleet.delete.assert_called_once()
        mock_info.assert_called_once()
        args, kwargs = mock_info.call_args

        self.assertTrue(
            any("Closing: Test reason" in str(x) for x in args + tuple(kwargs.values()))
        )

    def test_does_not_fail_with_empty_reason(self):
        """
        Test that _close_esi_fleet does not fail when given an empty reason.

        :return:
        :rtype:
        """

        mock_fleet = MagicMock()

        with patch("fleetfinder.tasks.logger.info") as mock_info:
            _close_esi_fleet(fleet=mock_fleet, reason="")

        mock_fleet.delete.assert_called_once()
        mock_info.assert_called_once()
        args, kwargs = mock_info.call_args

        self.assertTrue(
            any("Closing: " in str(x) for x in args + tuple(kwargs.values()))
        )


class TestHelperEsiFleetErrorHandling(BaseTestCase):
    """
    Tests for the _esi_fleet_error_handling helper function.
    """

    def test_closes_fleet_when_error_count_exceeds_limit(self):
        """
        Test that _esi_fleet_error_handling closes the fleet when error count exceeds limit.

        :return:
        :rtype:
        """

        mock_fleet = MagicMock()
        mock_fleet.last_esi_error = Fleet.EsiError.NO_FLEET
        mock_fleet.last_esi_error_time = timezone.now() - timedelta(
            seconds=ESI_ERROR_GRACE_TIME - 10
        )
        mock_fleet.esi_error_count = ESI_MAX_ERROR_COUNT

        with patch("fleetfinder.tasks._close_esi_fleet") as mock_close_fleet:
            _esi_fleet_error_handling(
                fleet=mock_fleet, error_key=Fleet.EsiError.NO_FLEET
            )

        mock_close_fleet.assert_called_once_with(
            fleet=mock_fleet, reason=Fleet.EsiError.NO_FLEET.label
        )

    def test_increments_error_count_for_same_error_within_grace_period(self):
        """
        Test that _esi_fleet_error_handling increments error count for the same error within grace period.

        :return:
        :rtype:
        """

        mock_fleet = MagicMock()
        mock_fleet.last_esi_error = Fleet.EsiError.NO_FLEET
        mock_fleet.last_esi_error_time = timezone.now() - timedelta(
            seconds=ESI_ERROR_GRACE_TIME - 10
        )
        mock_fleet.esi_error_count = 1

        _esi_fleet_error_handling(fleet=mock_fleet, error_key=Fleet.EsiError.NO_FLEET)

        self.assertEqual(mock_fleet.esi_error_count, 2)
        mock_fleet.save.assert_called_once()

    def test_resets_error_count_for_new_error(self):
        """
        Test that _esi_fleet_error_handling resets error count for a new error.

        :return:
        :rtype:
        """

        mock_fleet = MagicMock()
        mock_fleet.last_esi_error = Fleet.EsiError.NO_FLEET
        mock_fleet.last_esi_error_time = timezone.now() - timedelta(
            seconds=ESI_ERROR_GRACE_TIME - 10
        )
        mock_fleet.esi_error_count = 3

        _esi_fleet_error_handling(
            fleet=mock_fleet, error_key=Fleet.EsiError.NOT_IN_FLEET
        )

        self.assertEqual(mock_fleet.esi_error_count, 1)
        self.assertEqual(mock_fleet.last_esi_error, Fleet.EsiError.NOT_IN_FLEET)
        mock_fleet.save.assert_called_once()

    def test_resets_error_count_for_same_error_outside_grace_period(self):
        """
        Test that _esi_fleet_error_handling resets error count for the same error outside grace period.

        :return:
        :rtype:
        """

        mock_fleet = MagicMock()
        mock_fleet.last_esi_error = Fleet.EsiError.NO_FLEET
        mock_fleet.last_esi_error_time = timezone.now() - timedelta(
            seconds=ESI_ERROR_GRACE_TIME + 10
        )
        mock_fleet.esi_error_count = 3

        _esi_fleet_error_handling(fleet=mock_fleet, error_key=Fleet.EsiError.NO_FLEET)

        self.assertEqual(mock_fleet.esi_error_count, 1)
        mock_fleet.save.assert_called_once()


class TestHelperGetFleetAggregate(BaseTestCase):
    """
    Tests for the _get_fleet_aggregate helper function.
    """

    def test_returns_correct_counts_for_valid_fleet_infos(self):
        """
        Test that _get_fleet_aggregate returns correct counts for valid fleet_infos.

        :return:
        :rtype:
        """

        fleet_infos = [
            {"ship_type_name": "Cruiser"},
            {"ship_type_name": "Cruiser"},
            {"ship_type_name": "Battleship"},
        ]

        result = _get_fleet_aggregate(fleet_infos)

        self.assertEqual(result, {"Cruiser": 2, "Battleship": 1})

    def test_returns_empty_dict_for_empty_fleet_infos(self):
        """
        Test that _get_fleet_aggregate returns an empty dictionary for empty fleet_infos.

        :return:
        :rtype:
        """

        fleet_infos = []

        result = _get_fleet_aggregate(fleet_infos)

        self.assertEqual(result, {})

    def test_returns_only_valid_ship_type_names(self):
        """
        Test that _get_fleet_aggregate returns only valid ship type names.

        :return:
        :rtype:
        """

        fleet_infos = [
            {"ship_type_name": "Cruiser"},
            {},
            {"ship_type_name": None},
            {"ship_type_name": "Battleship"},
            {"other_key": "Frigate"},
        ]

        result = _get_fleet_aggregate(fleet_infos)

        self.assertEqual(result, {"Cruiser": 1, "Battleship": 1})


class TestHelperCheckForEsiFleet(BaseTestCase):
    """
    Tests for the _check_for_esi_fleet helper function.
    """

    @patch("fleetfinder.tasks.Token.get_token")
    def test_retrieves_fleet_data_when_fleet_exists(self, mock_get_token):
        """
        Test that _check_for_esi_fleet retrieves fleet data when the fleet exists.

        :param mock_get_token:
        :type mock_get_token:
        :return:
        :rtype:
        """

        mock_get_token.return_value = MagicMock()
        mock_esi_client = MagicMock()
        mock_esi_client.Fleets.GetCharactersCharacterIdFleet.return_value.result.return_value = {
            "fleet_id": 12345
        }

        fleet = Mock(
            fleet_commander=Mock(character_id=67890), name="Test Fleet", fleet_id=12345
        )

        with patch("fleetfinder.tasks.esi", Mock(client=mock_esi_client)):
            result = _check_for_esi_fleet(fleet)

        self.assertEqual(result["fleet"], {"fleet_id": 12345})
        self.assertEqual(result["token"], mock_get_token.return_value)
        mock_esi_client.Fleets.GetCharactersCharacterIdFleet.return_value.result.assert_called_once()

    def test_handles_http_client_error_for_fleet_not_found(self):
        """
        Test that _check_for_esi_fleet handles HTTPClientError for fleet not found.

        :return:
        :rtype:
        """

        mock_fleet = MagicMock()
        mock_token = MagicMock()

        # concrete response whose .result() raises an instance of HTTPClientError (404)
        mock_response = MagicMock()
        mock_response.result.side_effect = HTTPClientError(404, {}, b"")

        mock_client = MagicMock()
        mock_client.Fleets.GetCharactersCharacterIdFleet.return_value = mock_response

        with patch("fleetfinder.tasks.Token.get_token", return_value=mock_token):
            with patch("fleetfinder.tasks.esi", Mock(client=mock_client)):
                with patch(
                    "fleetfinder.tasks._esi_fleet_error_handling"
                ) as mock_error_handling:
                    _check_for_esi_fleet(fleet=mock_fleet)

        mock_client.Fleets.GetCharactersCharacterIdFleet.assert_called_once()
        mock_response.result.assert_called_once()
        mock_error_handling.assert_called_once_with(
            error_key=Fleet.EsiError.NOT_IN_FLEET, fleet=mock_fleet
        )

    def test_handles_http_client_error_for_other_errors(self):
        """
        Test that _check_for_esi_fleet handles HTTPClientError for other errors.

        :return:
        :rtype:
        """

        mock_fleet = MagicMock()
        mock_token = MagicMock()

        # concrete response whose .result() raises an instance of HTTPClientError (403)
        mock_response = MagicMock()
        mock_response.result.side_effect = HTTPClientError(403, {}, b"")

        mock_client = MagicMock()
        mock_client.Fleets.GetCharactersCharacterIdFleet.return_value = mock_response

        with patch("fleetfinder.tasks.Token.get_token", return_value=mock_token):
            with patch("fleetfinder.tasks.esi", Mock(client=mock_client)):
                with patch(
                    "fleetfinder.tasks._esi_fleet_error_handling"
                ) as mock_error_handling:
                    _check_for_esi_fleet(fleet=mock_fleet)

        mock_client.Fleets.GetCharactersCharacterIdFleet.assert_called_once()
        mock_response.result.assert_called_once()
        mock_error_handling.assert_called_once_with(
            error_key=Fleet.EsiError.NO_FLEET, fleet=mock_fleet
        )

    def test_handles_generic_exception(self):
        """
        Test that _check_for_esi_fleet handles a generic exception.

        :return:
        :rtype:
        """

        mock_fleet = MagicMock()

        mock_esi_client = MagicMock()
        mock_esi_client.Fleets.GetCharactersCharacterIdFleet.return_value.result.side_effect = (
            Exception
        )

        with patch("fleetfinder.tasks.Token.get_token"):
            with patch("fleetfinder.tasks.esi", Mock(client=mock_esi_client)):
                with patch(
                    "fleetfinder.tasks._esi_fleet_error_handling"
                ) as mock_error_handling:
                    _check_for_esi_fleet(fleet=mock_fleet)

        mock_error_handling.assert_called_once_with(
            error_key=Fleet.EsiError.NO_FLEET, fleet=mock_fleet
        )


class TestHelperProcessFleet(BaseTestCase):
    """
    Tests for the _process_fleet helper function.
    """

    def test_processes_fleet_successfully(self):
        """
        Test that _process_fleet processes a fleet successfully.

        :return:
        :rtype:
        """

        mock_fleet = MagicMock()
        mock_fleet.name = "Test Fleet"
        mock_fleet.fleet_commander.character_id = 12345
        mock_fleet.fleet_id = 67890

        mock_esi_fleet = {"fleet": MagicMock(fleet_id=67890), "token": MagicMock()}

        mock_esi_client = MagicMock()
        mock_esi_client.Fleets.GetFleetsFleetIdMembers.return_value.result.return_value = (
            []
        )

        with patch(
            "fleetfinder.tasks._check_for_esi_fleet", return_value=mock_esi_fleet
        ) as mock_check:
            with patch("fleetfinder.tasks.esi", Mock(client=mock_esi_client)):
                _process_fleet(fleet=mock_fleet)

        mock_check.assert_called_once_with(fleet=mock_fleet)
        mock_esi_client.Fleets.GetFleetsFleetIdMembers.assert_called_once_with(
            fleet_id=67890, token=mock_esi_fleet["token"]
        )

    def test_skips_processing_when_fleet_does_not_exist(self):
        """
        Test that _process_fleet skips processing when fleet does not exist.

        :return:
        :rtype:
        """

        mock_fleet = MagicMock()

        with patch(
            "fleetfinder.tasks._check_for_esi_fleet", return_value=False
        ) as mock_check:
            _process_fleet(fleet=mock_fleet)

        mock_check.assert_called_once_with(fleet=mock_fleet)

    def test_handles_fleet_commander_change(self):
        """
        Test that _process_fleet handles fleet commander change.

        :return:
        :rtype:
        """

        mock_fleet = MagicMock()
        mock_fleet.name = "Test Fleet"
        mock_fleet.fleet_commander.character_id = 12345
        mock_fleet.fleet_id = 67890

        mock_esi_fleet = {"fleet": MagicMock(fleet_id=11111), "token": MagicMock()}

        with patch(
            "fleetfinder.tasks._check_for_esi_fleet", return_value=mock_esi_fleet
        ):
            with patch(
                "fleetfinder.tasks._esi_fleet_error_handling"
            ) as mock_error_handling:
                _process_fleet(fleet=mock_fleet)

        mock_error_handling.assert_called_once_with(
            fleet=mock_fleet, error_key=Fleet.EsiError.FC_CHANGED_FLEET
        )

    def test_handles_not_fleet_boss_error(self):
        """
        Test that _process_fleet handles not fleet boss error.

        :return:
        :rtype:
        """

        mock_fleet = MagicMock()
        mock_fleet.name = "Test Fleet"
        mock_fleet.fleet_commander.character_id = 12345
        mock_fleet.fleet_id = 67890

        mock_esi_fleet = {"fleet": MagicMock(fleet_id=67890), "token": MagicMock()}

        mock_esi_client = MagicMock()
        mock_esi_client.Fleets.GetFleetsFleetIdMembers.return_value.result.side_effect = (
            Exception()
        )

        with patch(
            "fleetfinder.tasks._check_for_esi_fleet", return_value=mock_esi_fleet
        ):
            with patch("fleetfinder.tasks.esi", Mock(client=mock_esi_client)):
                with patch(
                    "fleetfinder.tasks._esi_fleet_error_handling"
                ) as mock_error_handling:
                    _process_fleet(fleet=mock_fleet)

        mock_error_handling.assert_called_once_with(
            fleet=mock_fleet, error_key=Fleet.EsiError.NOT_FLEETBOSS
        )


class TestSendFleetInvitation(BaseTestCase):
    """
    Tests for the send_fleet_invitation function.
    """

    def test_sends_invitations_to_all_characters_successfully(self):
        """
        Test that send_fleet_invitation sends invitations to all characters successfully.

        :return:
        :rtype:
        """

        mock_fleet = MagicMock()
        mock_fleet.fleet_commander.character_id = 12345

        mock_token = MagicMock()
        mock_character_ids = [111, 222, 333]

        with patch("fleetfinder.tasks.Fleet.objects.get", return_value=mock_fleet):
            with patch("fleetfinder.tasks.Token.get_token", return_value=mock_token):
                with patch(
                    "fleetfinder.tasks._send_invitation"
                ) as mock_send_invitation:
                    send_fleet_invitation(
                        fleet_id=67890, character_ids=mock_character_ids
                    )

        mock_send_invitation.assert_any_call(
            character_id=111, fleet_commander_token=mock_token, fleet_id=67890
        )
        mock_send_invitation.assert_any_call(
            character_id=222, fleet_commander_token=mock_token, fleet_id=67890
        )
        mock_send_invitation.assert_any_call(
            character_id=333, fleet_commander_token=mock_token, fleet_id=67890
        )
        self.assertEqual(mock_send_invitation.call_count, 3)

    def test_handles_empty_character_list_gracefully(self):
        """
        Test that send_fleet_invitation handles an empty character list gracefully.

        :return:
        :rtype:
        """

        mock_fleet = MagicMock()
        mock_fleet.fleet_commander.character_id = 12345

        with patch("fleetfinder.tasks.Fleet.objects.get", return_value=mock_fleet):
            with patch("fleetfinder.tasks.Token.get_token"):
                with patch(
                    "fleetfinder.tasks._send_invitation"
                ) as mock_send_invitation:
                    send_fleet_invitation(fleet_id=67890, character_ids=[])

        mock_send_invitation.assert_not_called()

    def test_raises_exception_when_fleet_not_found(self):
        """
        Test that send_fleet_invitation raises an exception when the fleet is not found.

        :return:
        :rtype:
        """

        with patch(
            "fleetfinder.tasks.Fleet.objects.get", side_effect=Fleet.DoesNotExist
        ):
            with self.assertRaises(Fleet.DoesNotExist):
                send_fleet_invitation(fleet_id=67890, character_ids=[111, 222, 333])

    def test_raises_exception_when_token_retrieval_fails(self):
        """
        Test that send_fleet_invitation raises an exception when token retrieval fails.

        :return:
        :rtype:
        """

        mock_fleet = MagicMock()
        mock_fleet.fleet_commander.character_id = 12345

        with patch("fleetfinder.tasks.Fleet.objects.get", return_value=mock_fleet):
            with patch("fleetfinder.tasks.Token.get_token", side_effect=Exception):
                with self.assertRaises(Exception):
                    send_fleet_invitation(fleet_id=67890, character_ids=[111, 222, 333])


class TestCheckFleetAdverts(BaseTestCase):
    """
    Tests for the check_fleet_adverts function.
    """

    @patch("fleetfinder.tasks.Fleet.objects.all")
    @patch("fleetfinder.tasks.logger.info")
    def test_logs_message_when_no_fleets_to_process(self, mock_logger, mock_fleets):
        """
        Test that check_fleet_adverts logs a message when there are no fleets to process.

        :param mock_logger:
        :type mock_logger:
        :param mock_fleets:
        :type mock_fleets:
        :return:
        :rtype:
        """

        mock_fleets.return_value.exists.return_value = False

        check_fleet_adverts()

        mock_logger.assert_called_once_with(
            "No registered fleets found. Nothing to do..."
        )

    @patch("fleetfinder.tasks.Fleet.objects.all")
    @patch("fleetfinder.tasks.logger.info")
    @patch("fleetfinder.tasks._process_fleet")
    def test_processes_all_fleets_when_fleets_exist(
        self, mock_process_fleet, mock_logger, mock_fleets
    ):
        """
        Test that check_fleet_adverts processes all fleets when fleets exist.

        :param mock_process_fleet:
        :type mock_process_fleet:
        :param mock_logger:
        :type mock_logger:
        :param mock_fleets:
        :type mock_fleets:
        :return:
        :rtype:
        """

        mock_fleet_1 = Mock()
        mock_fleet_2 = Mock()
        mock_fleets.return_value.exists.return_value = True
        mock_fleets.return_value.count.return_value = 2
        mock_fleets.return_value.__iter__.return_value = iter(
            [mock_fleet_1, mock_fleet_2]
        )

        check_fleet_adverts()

        mock_logger.assert_any_call("Processing 2 registered fleets...")
        mock_process_fleet.assert_any_call(fleet=mock_fleet_1)
        mock_process_fleet.assert_any_call(fleet=mock_fleet_2)

    @patch("fleetfinder.tasks.Fleet.objects.all")
    @patch("fleetfinder.tasks.logger.info")
    @patch("fleetfinder.tasks._process_fleet")
    def test_handles_empty_fleet_queryset_gracefully(
        self, mock_process_fleet, mock_logger, mock_fleets
    ):
        """
        Test that check_fleet_adverts handles an empty fleet queryset gracefully.

        :param mock_process_fleet:
        :type mock_process_fleet:
        :param mock_logger:
        :type mock_logger:
        :param mock_fleets:
        :type mock_fleets:
        :return:
        :rtype:
        """

        mock_fleets.return_value.exists.return_value = True
        mock_fleets.return_value.count.return_value = 0
        mock_fleets.return_value.__iter__.return_value = iter([])

        check_fleet_adverts()

        mock_logger.assert_called_once_with("Processing 0 registered fleets...")
        mock_process_fleet.assert_not_called()


class TestHelperMakeNameLookup(BaseTestCase):
    """
    Tests for the _make_name_lookup helper function.
    """

    def test_creates_lookup_from_dicts(self):
        """
        Test that _make_name_lookup creates a lookup from a list of dictionaries.

        :return:
        :rtype:
        """

        input_data = [{"id": 1, "name": "Name1"}, {"id": 2, "name": "Name2"}]
        expected_output = {1: "Name1", 2: "Name2"}

        result = _make_name_lookup(input_data)

        self.assertEqual(result, expected_output)

    def test_creates_lookup_from_objects(self):
        """
        Test that _make_name_lookup creates a lookup from a list of objects.

        :return:
        :rtype:
        """

        mock_item1 = MagicMock()
        mock_item1.id = 1
        mock_item1.name = "Name1"
        mock_item2 = MagicMock()
        mock_item2.id = 2
        mock_item2.name = "Name2"
        input_data = [mock_item1, mock_item2]
        expected_output = {1: "Name1", 2: "Name2"}

        result = _make_name_lookup(input_data)

        self.assertEqual(result, expected_output)

    def test_handles_mixed_input_types(self):
        """
        Test that _make_name_lookup handles mixed input types (dicts and objects).

        :return:
        :rtype:
        """

        mock_item = MagicMock()
        mock_item.id = 3
        mock_item.name = "Name3"
        input_data = [{"id": 1, "name": "Name1"}, mock_item, {"id": 2, "name": "Name2"}]
        expected_output = {1: "Name1", 2: "Name2", 3: "Name3"}

        result = _make_name_lookup(input_data)

        self.assertEqual(result, expected_output)

    def test_ignores_items_with_missing_id_or_name(self):
        """
        Test that _make_name_lookup ignores items with missing id or name.

        :return:
        :rtype:
        """

        input_data = [
            {"id": 1, "name": "Name1"},
            {"id": None, "name": "Name2"},
            {"id": 2, "name": None},
            {"name": "Name3"},
            {"id": 3},
        ]
        expected_output = {1: "Name1"}

        result = _make_name_lookup(input_data)

        self.assertEqual(result, expected_output)

    def test_returns_empty_dict_for_empty_input(self):
        """
        Test that _make_name_lookup returns an empty dictionary for empty input.

        :return:
        :rtype:
        """

        input_data = []
        expected_output = {}

        result = _make_name_lookup(input_data)

        self.assertEqual(result, expected_output)

    def test_skips_none_items_in_input(self):
        """
        Test that _make_name_lookup skips None items in the input list.

        :return:
        :rtype:
        """

        input_data = [{"id": 1, "name": "Name1"}, None, {"id": 2, "name": "Name2"}]
        expected_output = {1: "Name1", 2: "Name2"}

        result = _make_name_lookup(input_data)

        self.assertEqual(result, expected_output)


class TestHelperFetchChunk(BaseTestCase):
    """
    Tests for the _fetch_chunk helper function.
    """

    def test_fetches_names_for_valid_ids(self):
        """
        Test that _fetch_chunk fetches names for valid IDs.

        :return:
        :rtype:
        """

        ids = [1, 2, 3]
        mock_result = [
            {"id": 1, "name": "Name1"},
            {"id": 2, "name": "Name2"},
            {"id": 3, "name": "Name3"},
        ]

        mock_client = MagicMock()
        mock_client.Universe.PostUniverseNames.return_value.result.return_value = (
            mock_result
        )

        with patch("fleetfinder.tasks.esi", Mock(client=mock_client)):
            result = _fetch_chunk(ids)

        self.assertEqual(result, mock_result)
        mock_client.Universe.PostUniverseNames.assert_called_once_with(body=ids)

    def test_handles_single_id_failure_gracefully(self):
        """
        Test that _fetch_chunk handles single ID failure gracefully.

        :return:
        :rtype:
        """

        ids = [1]

        mock_client = MagicMock()
        mock_client.Universe.PostUniverseNames.return_value.result.side_effect = (
            Exception()
        )

        with patch("fleetfinder.tasks.esi", Mock(client=mock_client)):
            result = _fetch_chunk(ids)

        self.assertEqual(result, [])
        mock_client.Universe.PostUniverseNames.assert_called_once_with(body=ids)

    def test_retries_with_split_on_failure(self):
        """
        Test that _fetch_chunk retries with split on failure.

        :return:
        :rtype:
        """

        ids = [1, 2, 3, 4]
        mock_result_1 = [{"id": 1, "name": "Name1"}, {"id": 2, "name": "Name2"}]
        mock_result_2 = [{"id": 3, "name": "Name3"}, {"id": 4, "name": "Name4"}]

        mock_client = MagicMock()
        mock_client.Universe.PostUniverseNames.return_value.result.side_effect = [
            Exception(),
            mock_result_1,
            mock_result_2,
        ]

        with patch("fleetfinder.tasks.esi", Mock(client=mock_client)):
            result = _fetch_chunk(ids)

        self.assertEqual(result, mock_result_1 + mock_result_2)
        self.assertEqual(mock_client.Universe.PostUniverseNames.call_count, 3)
        mock_client.Universe.PostUniverseNames.assert_any_call(body=[1, 2])
        mock_client.Universe.PostUniverseNames.assert_any_call(body=[3, 4])

    def test_handles_empty_id_list(self):
        """
        Test that _fetch_chunk handles an empty ID list.

        :return:
        :rtype:
        """

        ids = []

        mock_client = MagicMock()
        mock_client.Universe.PostUniverseNames.return_value.result.return_value = []

        with patch("fleetfinder.tasks.esi", Mock(client=mock_client)):
            result = _fetch_chunk(ids)

        self.assertEqual(result, [])


class TestGetFleetComposition(BaseTestCase):
    """
    Tests for the get_fleet_composition function.
    """

    def test_retrieves_fleet_composition_successfully(self):
        """
        Test that get_fleet_composition retrieves fleet composition successfully.

        :return:
        :rtype:
        """

        mock_fleet = MagicMock()
        mock_fleet.fleet_commander.character_id = 1
        mock_fleet.fleet_commander.character_name = "Commander"
        mock_fleet.name = "Test Fleet"
        mock_fleet.fleet_id = 67890

        mock_token = MagicMock()

        def _make_member(character_id, solar_system_id, ship_type_id, takes_fleet_warp):
            """
            Helper to create a mock fleet member.

            :param character_id:
            :type character_id:
            :param solar_system_id:
            :type solar_system_id:
            :param ship_type_id:
            :type ship_type_id:
            :param takes_fleet_warp:
            :type takes_fleet_warp:
            :return:
            :rtype:
            """

            m = MagicMock()
            m.character_id = character_id
            m.solar_system_id = solar_system_id
            m.ship_type_id = ship_type_id
            m.takes_fleet_warp = takes_fleet_warp
            m.dict.return_value = {
                "character_id": character_id,
                "solar_system_id": solar_system_id,
                "ship_type_id": ship_type_id,
            }
            return m

        mock_fleet_infos = [
            _make_member(1, 101, 201, True),
            _make_member(2, 102, 202, False),
        ]

        mock_name_lookup = {
            1: "Character1",
            2: "Character2",
            101: "SolarSystem1",
            102: "SolarSystem2",
            201: "ShipType1",
            202: "ShipType2",
        }

        mock_esi_client = MagicMock()
        mock_esi_client.Fleets.GetFleetsFleetIdMembers.return_value.result.return_value = (
            mock_fleet_infos
        )

        with patch("fleetfinder.tasks.Fleet.objects.get", return_value=mock_fleet):
            with patch("fleetfinder.tasks.Token.get_token", return_value=mock_token):
                with patch("fleetfinder.tasks.esi", Mock(client=mock_esi_client)):
                    with patch("fleetfinder.tasks._fetch_chunk") as mock_fetch_chunk:
                        mock_fetch_chunk.side_effect = lambda ids: [
                            {"id": id_, "name": mock_name_lookup[id_]} for id_ in ids
                        ]

                        with patch(
                            "fleetfinder.tasks._get_fleet_aggregate"
                        ) as mock_aggregate:
                            mock_aggregate.return_value = {
                                "ShipType1": 1,
                                "ShipType2": 1,
                            }

                            result = get_fleet_composition(fleet_id=67890)

        self.assertEqual(
            result.fleet,
            [
                {
                    "character_id": 1,
                    "solar_system_id": 101,
                    "ship_type_id": 201,
                    "takes_fleet_warp": True,
                    "character_name": "Character1",
                    "solar_system_name": "SolarSystem1",
                    "ship_type_name": "ShipType1",
                    "is_fleet_boss": True,
                },
                {
                    "character_id": 2,
                    "solar_system_id": 102,
                    "ship_type_id": 202,
                    "takes_fleet_warp": False,
                    "character_name": "Character2",
                    "solar_system_name": "SolarSystem2",
                    "ship_type_name": "ShipType2",
                    "is_fleet_boss": False,
                },
            ],
        )
        self.assertEqual(result.aggregate, {"ShipType1": 1, "ShipType2": 1})

    def test_raises_exception_when_fleet_does_not_exist(self):
        """
        Test that get_fleet_composition raises an exception when the fleet does not exist.

        :return:
        :rtype:
        """

        with patch(
            "fleetfinder.tasks.Fleet.objects.get", side_effect=Fleet.DoesNotExist
        ):
            with self.assertRaises(Fleet.DoesNotExist):
                get_fleet_composition(fleet_id=67890)

    def test_raises_runtime_error_on_unexpected_exception(self):
        """
        Test that get_fleet_composition raises RuntimeError on unexpected exception.

        :return:
        :rtype:
        """

        # Prepare an ESI operation whose .result() raises an unexpected exception
        mock_operation = MagicMock()
        mock_operation.result.side_effect = Exception("unexpected error")
        mock_esi_client = MagicMock()
        mock_esi_client.Fleets.GetFleetsFleetIdMembers.return_value = mock_operation

        # Minimal fleet object returned by Fleet.objects.get(...)
        fleet = Mock(
            fleet_id=42,
            name="Test Fleet",
            fleet_commander=Mock(character_id=1, character_name="Commander"),
        )

        with (
            patch("fleetfinder.tasks.Fleet.objects.get", return_value=fleet),
            patch("fleetfinder.tasks.esi", Mock(client=mock_esi_client)),
            patch("fleetfinder.tasks.Token.get_token", return_value=MagicMock()),
            patch("fleetfinder.tasks.logger") as mock_logger,
        ):
            # RuntimeError should be raised when the ESI call fails unexpectedly
            with self.assertRaises(RuntimeError):
                get_fleet_composition(42)

            # Ensure an error was logged with the expected content
            expected = "Failed to get fleet composition for fleet 42"
            found = False

            for call in mock_logger.method_calls:
                name, args, kwargs = call

                if name == "error" and args and expected in str(args[0]):
                    found = True

                    break

            self.assertTrue(found, "Expected error log message not found")

    def test_handles_handles_empty_fleet_info_gracefully(self):
        """
        Test that get_fleet_composition handles empty fleet info gracefully.

        :return:
        :rtype:
        """

        mock_fleet = MagicMock()
        mock_fleet.fleet_commander.character_id = 12345
        mock_fleet.fleet_id = 67890

        mock_token = MagicMock()

        mock_esi_client = MagicMock()
        mock_esi_client.Fleets.GetFleetsFleetIdMembers.return_value.result.return_value = (
            []
        )

        with patch("fleetfinder.tasks.Fleet.objects.get", return_value=mock_fleet):
            with patch("fleetfinder.tasks.Token.get_token", return_value=mock_token):
                with patch("fleetfinder.tasks.esi", Mock(client=mock_esi_client)):
                    result = get_fleet_composition(fleet_id=67890)

        self.assertEqual(result.fleet, [])
        self.assertEqual(result.aggregate, {})
