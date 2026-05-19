import json
import os
from types import SimpleNamespace
from unittest.mock import patch

from django.contrib.auth.models import User
from django.test import TestCase
from django.utils.timezone import now

from allianceauth.tests.auth_utils import AuthUtils

from ..managers import SRPManager
from ..models import SrpFleetMain, SrpUserRequest

MODULE_PATH = 'allianceauth.srp.managers'

currentdir = os.path.dirname(os.path.abspath(__file__))


def load_data(filename):
    """loads given JSON file from `testdata` sub folder and returns content"""
    with open(
        currentdir + f'/testdata/{filename}.json', encoding='utf-8'
    ) as f:
        data = json.load(f)

    return data


class TestSrpManager(TestCase):

    def test_can_extract_kill_id(self) -> None:
        link = 'https://zkillboard.com/kill/81973979/'
        expected = 81973979
        self.assertEqual(int(SRPManager.get_kill_id(link)), expected)

    @patch(MODULE_PATH + '.get_killmails_killmail_id_killmail_hash')
    @patch(MODULE_PATH + '.requests.get')
    def test_can_get_kill_data(self, mock_get, mock_get_killmail) -> None:
        mock_get.return_value.json.return_value = load_data(
            'zkillboard_killmail_api_81973979'
        )
        mock_get_killmail.return_value = SimpleNamespace(
            victim=SimpleNamespace(
                ship_type_id=19720,
                character_id=93330670,
            )
        )

        ship_type, ship_value, victim_id = SRPManager.get_kill_data(81973979)
        self.assertEqual(ship_type, 19720)
        self.assertEqual(ship_value, 3177859026.86)
        self.assertEqual(victim_id, 93330670)

    @patch(MODULE_PATH + '.requests.get')
    def test_invalid_id_for_zkb_raises_exception(self, mock_get) -> None:
        mock_get.return_value.json.return_value = ['']

        with self.assertRaises(ValueError):
            SRPManager.get_kill_data(81973979)

    @patch(MODULE_PATH + '.get_killmails_killmail_id_killmail_hash')
    @patch(MODULE_PATH + '.requests.get')
    def test_invalid_id_for_esi_raises_exception(
        self, mock_get, mock_get_killmail
    ):
        mock_get.return_value.json.return_value = load_data(
            'zkillboard_killmail_api_81973979'
        )
        mock_get_killmail.return_value = None

        with self.assertRaises(ValueError):
            SRPManager.get_kill_data(81973979)

    def test_pending_requests_count_for_user(self) -> None:
        user = AuthUtils.create_member("Bruce Wayne")

        # when no permission to approve SRP requests
        # then return None
        self.assertIsNone(SRPManager.pending_requests_count_for_user(user))

        # given permission to approve SRP requests
        # when no open requests
        # then return 0
        AuthUtils.add_permission_to_user_by_name("auth.srp_management", user)
        user = User.objects.get(pk=user.pk)
        self.assertEqual(SRPManager.pending_requests_count_for_user(user), 0)

        # given permission to approve SRP requests
        # when 1 pending request
        # then return 1
        fleet = SrpFleetMain.objects.create(fleet_time=now())
        SrpUserRequest.objects.create(
            killboard_link="https://zkillboard.com/kill/79111612/",
            srp_status="Pending",
            srp_fleet_main=fleet,
        )
        SrpUserRequest.objects.create(
            killboard_link="https://zkillboard.com/kill/79111612/",
            srp_status="Approved",
            srp_fleet_main=fleet,
        )
        self.assertEqual(SRPManager.pending_requests_count_for_user(user), 1)
