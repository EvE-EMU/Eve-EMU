from unittest.mock import Mock, patch

from django.contrib.sessions.middleware import SessionMiddleware
from django.test import RequestFactory, TestCase
from django.urls import reverse
from eveuniverse.models import EveEntity, EveType

from allianceauth.eveonline.models import EveCorporationInfo
from allianceauth.tests.auth_utils import AuthUtils
from app_utils.testing import create_user_from_evecharacter, json_response_to_python

from blueprints.models import Blueprint, Location, Owner, Request
from blueprints.views.blueprint_list import BlueprintListJson
from blueprints.views.regular_views import (
    add_corporation_blueprint_owner,
    add_personal_blueprint_owner,
    list_blueprints_ffd,
    list_user_owners,
    remove_owner,
)

from . import create_owner
from .testdata.load_entities import load_entities
from .testdata.load_eveuniverse import load_eveuniverse
from .testdata.load_locations import load_locations

MODELS_PATH = "blueprints.models"
VIEWS_PATH = "blueprints.views.regular_views"


def notification_count(user) -> int:
    return user.notification_set.filter(viewed=False).count()


class _TestCaseWithTestData(TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        super().setUpClass()
        load_eveuniverse()
        load_entities()
        load_locations()
        cls.owner = create_owner(character_id=1101, corporation_id=2101)
        cls.user_owner = cls.owner.character.user
        cls.corporation_2001 = EveEntity.objects.get(id=2101)
        cls.jita_44 = Location.objects.get(id=60003760)
        cls.blueprint = Blueprint.objects.create(
            location=cls.jita_44,
            eve_type=EveType.objects.get(id=33519),
            owner=cls.owner,
            runs=None,
            quantity=1,
            location_flag="AssetSafety",
            material_efficiency=0,
            time_efficiency=0,
            item_id=1,
        )
        cls.user_requestor, _ = create_user_from_evecharacter(
            1102,
            permissions=["blueprints.basic_access", "blueprints.request_blueprints"],
        )
        cls.user_other_approver, _ = create_user_from_evecharacter(
            1103,
            permissions=["blueprints.basic_access", "blueprints.manage_requests"],
        )


class TestBlueprintsData(_TestCaseWithTestData):
    @classmethod
    def setUpClass(cls) -> None:
        super().setUpClass()
        cls.factory = RequestFactory()
        cls.user_owner = AuthUtils.add_permission_to_user_by_name(
            "blueprints.view_blueprint_locations", cls.user_owner
        )

    def test_blueprints_data(self):
        request = self.factory.get(reverse("blueprints:list_blueprints"))
        request.user = self.user_owner
        response = BlueprintListJson.as_view()(request)
        self.assertEqual(response.status_code, 200)
        data = json_response_to_python(response)["data"]
        self.assertEqual(len(data), 1)
        row = data[0]
        self.assertEqual(row[1], "Mobile Tractor Unit Blueprint")
        self.assertEqual(row[9], "Jita IV - Moon 4 - Caldari Navy Assembly Plant")

    def test_my_requests_data(self):
        Request.objects.create(
            blueprint=self.blueprint,
            runs=None,
            requesting_user=self.user_owner,
            fulfulling_user=None,
            status="OP",
        )
        request = self.factory.get(reverse("blueprints:list_user_requests"))
        request.user = self.user_owner
        response = BlueprintListJson.as_view()(request)
        self.assertEqual(response.status_code, 200)
        data = json_response_to_python(response)["data"]
        self.assertEqual(len(data), 1)
        row = data[0]
        self.assertEqual(row[1], "Mobile Tractor Unit Blueprint")
        self.assertEqual(row[9], "Jita IV - Moon 4 - Caldari Navy Assembly Plant")

    def test_list_user_owners(self):
        request = self.factory.get(reverse("blueprints:list_user_owners"))
        request.user = self.user_owner
        response = list_user_owners(request)
        self.assertEqual(response.status_code, 200)
        data = json_response_to_python(response)
        self.assertEqual(len(data), 1)
        row = data[0]
        self.assertEqual(row["name"], "Lexcorp")
        self.assertEqual(row["type"], "corporate")

    @patch(VIEWS_PATH + ".messages")
    def test_remove_owner(self, mock_messages):
        request = self.factory.post(
            reverse("blueprints:remove_owner", args=[self.owner.pk])
        )
        request.user = self.user_owner
        response = remove_owner(request, self.owner.pk)
        self.assertEqual(response.status_code, 302)
        self.assertTrue(mock_messages.info.called)
        self.assertEqual(Owner.objects.filter(pk=self.owner.pk).first(), None)

    def test_should_handle_owner_without_character(self):
        # given
        Owner.objects.create(
            corporation=EveCorporationInfo.objects.get(corporation_id=2001)
        )  # owner without character
        request = self.factory.get(reverse("blueprints:list_blueprints"))
        request.user = self.user_owner
        # when
        response = BlueprintListJson.as_view()(request)
        # then
        self.assertEqual(response.status_code, 200)
        data = json_response_to_python(response)["data"]
        self.assertEqual(len(data), 1)
        row = data[0]
        self.assertEqual(row[1], "Mobile Tractor Unit Blueprint")
        self.assertEqual(row[9], "Jita IV - Moon 4 - Caldari Navy Assembly Plant")

    def test_should_handle_empty_owner(self):
        # given
        Owner.objects.create()  # empty owner
        request = self.factory.get(reverse("blueprints:list_blueprints"))
        request.user = self.user_owner
        # when
        response = BlueprintListJson.as_view()(request)
        # then
        self.assertEqual(response.status_code, 200)
        data = json_response_to_python(response)["data"]
        self.assertEqual(len(data), 1)
        row = data[0]
        self.assertEqual(row[1], "Mobile Tractor Unit Blueprint")
        self.assertEqual(row[9], "Jita IV - Moon 4 - Caldari Navy Assembly Plant")


class TestListBlueprintsFdd(TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        super().setUpClass()
        load_eveuniverse()
        load_entities()
        load_locations()
        cls.factory = RequestFactory()
        cls.owner_1001 = create_owner(character_id=1001, corporation_id=None)
        cls.owner_1001.character.user = AuthUtils.add_permission_to_user_by_name(
            "blueprints.view_blueprint_locations", cls.owner_1001.character.user
        )
        cls.owner_1002 = create_owner(character_id=1002, corporation_id=2001)

    def test_should_return_list_of_options(self):
        # given
        Blueprint.objects.create(
            location=Location.objects.get(id=60003760),
            eve_type=EveType.objects.get(id=33519),
            owner=self.owner_1001,
            runs=10,
            location_flag="AssetSafety",
            material_efficiency=10,
            time_efficiency=30,
            item_id=1,
        )
        Blueprint.objects.create(
            location=Location.objects.get(id=1000000000001),
            eve_type=EveType.objects.get(id=33519),
            owner=self.owner_1002,
            location_flag="AssetSafety",
            material_efficiency=20,
            time_efficiency=40,
            item_id=2,
        )
        request = self.factory.get(
            reverse("blueprints:list_blueprints_ffd")
            + "?columns=location,owner,material_efficiency,time_efficiency,is_original"
        )
        request.user = self.owner_1001.character.user
        # when
        response = list_blueprints_ffd(request)
        # then
        self.assertEqual(response.status_code, 200)
        data = json_response_to_python(response)
        self.assertDictEqual(
            data,
            {
                "location": [
                    "Amamake - Test Structure Alpha",
                    "Jita IV - Moon 4 - Caldari Navy Assembly Plant",
                ],
                "owner": ["Bruce Wayne", "Wayne Technologies"],
                "material_efficiency": [10, 20],
                "time_efficiency": [30, 40],
                "is_original": ["no", "yes"],
            },
        )


class TestRequestWorkflow(_TestCaseWithTestData):
    @classmethod
    def setUpClass(cls) -> None:
        super().setUpClass()

    @patch(VIEWS_PATH + ".messages")
    def test_should_create_new_request(self, mock_messages):
        # given
        self.client.force_login(self.user_requestor)
        # when
        response = self.client.post(
            "/blueprints/requests/add", data={"pk": self.blueprint.pk}
        )
        # then
        self.assertEqual(response.status_code, 302)
        self.assertTrue(mock_messages.info.called)
        user_request = Request.objects.filter(blueprint=self.blueprint).first()
        self.assertEqual(user_request.status, Request.STATUS_OPEN)
        self.assertEqual(user_request.requesting_user, self.user_requestor)
        self.assertEqual(notification_count(self.user_requestor), 0)
        self.assertEqual(notification_count(self.user_owner), 1)
        self.assertEqual(notification_count(self.user_other_approver), 1)

    @patch(VIEWS_PATH + ".messages")
    def test_should_mark_request_cancelled_by_requestor(self, mock_messages):
        # given
        user_request = Request.objects.create(
            blueprint=self.blueprint,
            runs=None,
            requesting_user=self.user_requestor,
            status=Request.STATUS_IN_PROGRESS,
        )
        self.client.force_login(self.user_requestor)
        # when
        response = self.client.post(f"/blueprints/requests/{user_request.pk}/cancel")
        # then
        self.assertEqual(response.status_code, 302)
        self.assertTrue(mock_messages.info.called)
        user_request.refresh_from_db()
        self.assertEqual(user_request.status, Request.STATUS_CANCELLED)
        self.assertIsNone(user_request.fulfulling_user)
        self.assertEqual(notification_count(self.user_requestor), 0)
        self.assertEqual(notification_count(self.user_owner), 1)
        self.assertEqual(notification_count(self.user_other_approver), 1)

    @patch(VIEWS_PATH + ".messages")
    def test_should_mark_request_as_in_progress(self, mock_messages):
        # given
        user_request = Request.objects.create(
            blueprint=self.blueprint,
            runs=None,
            requesting_user=self.user_requestor,
            status=Request.STATUS_OPEN,
        )
        self.client.force_login(self.user_owner)
        # when
        response = self.client.post(
            f"/blueprints/requests/{user_request.pk}/in_progress"
        )
        # then
        self.assertEqual(response.status_code, 302)
        self.assertTrue(mock_messages.info.called)
        user_request.refresh_from_db()
        self.assertEqual(user_request.status, Request.STATUS_IN_PROGRESS)
        self.assertEqual(notification_count(self.user_requestor), 1)
        self.assertEqual(notification_count(self.user_owner), 0)
        self.assertEqual(notification_count(self.user_other_approver), 1)

    @patch(VIEWS_PATH + ".messages")
    def test_should_mark_request_as_fulfilled(self, mock_messages):
        # given
        user_request = Request.objects.create(
            blueprint=self.blueprint,
            runs=None,
            requesting_user=self.user_requestor,
            status=Request.STATUS_IN_PROGRESS,
        )
        self.client.force_login(self.user_owner)
        # when
        response = self.client.post(f"/blueprints/requests/{user_request.pk}/fulfill")
        # then
        self.assertEqual(response.status_code, 302)
        self.assertTrue(mock_messages.info.called)
        user_request.refresh_from_db()
        self.assertEqual(user_request.status, Request.STATUS_FULFILLED)
        self.assertEqual(user_request.fulfulling_user, self.user_owner)
        self.assertEqual(notification_count(self.user_requestor), 1)
        self.assertEqual(notification_count(self.user_owner), 0)
        self.assertEqual(notification_count(self.user_other_approver), 0)

    @patch(VIEWS_PATH + ".messages")
    def test_should_mark_request_as_cancelled_by_owner(self, mock_messages):
        # given
        user_request = Request.objects.create(
            blueprint=self.blueprint,
            runs=None,
            requesting_user=self.user_requestor,
            status=Request.STATUS_IN_PROGRESS,
        )
        self.client.force_login(self.user_owner)
        # when
        response = self.client.post(f"/blueprints/requests/{user_request.pk}/cancel")
        # then
        self.assertEqual(response.status_code, 302)
        self.assertTrue(mock_messages.info.called)
        user_request.refresh_from_db()
        self.assertEqual(user_request.status, Request.STATUS_CANCELLED)
        self.assertIsNone(user_request.fulfulling_user)
        self.assertEqual(notification_count(self.user_requestor), 1)
        self.assertEqual(notification_count(self.user_owner), 0)
        self.assertEqual(notification_count(self.user_other_approver), 1)

    @patch(VIEWS_PATH + ".messages")
    def test_should_mark_request_as_reopened(self, mock_messages):
        # given
        user_request = Request.objects.create(
            blueprint=self.blueprint,
            runs=None,
            requesting_user=self.user_requestor,
            fulfulling_user=self.user_owner,
            status=Request.STATUS_IN_PROGRESS,
        )
        self.client.force_login(self.user_owner)
        # when
        response = self.client.post(f"/blueprints/requests/{user_request.pk}/open")
        # then
        self.assertEqual(response.status_code, 302)
        self.assertTrue(mock_messages.info.called)
        user_request.refresh_from_db()
        self.assertEqual(user_request.status, Request.STATUS_OPEN)
        self.assertIsNone(user_request.fulfulling_user)
        self.assertEqual(notification_count(self.user_requestor), 1)
        self.assertEqual(notification_count(self.user_owner), 0)
        self.assertEqual(notification_count(self.user_other_approver), 1)


class TestOtherViews(_TestCaseWithTestData):
    @classmethod
    def setUpClass(cls) -> None:
        super().setUpClass()

    def test_can_open_index_by_requestor(self):
        # given
        self.client.force_login(self.user_requestor)
        # when
        response = self.client.get("/blueprints/")
        # then
        self.assertTemplateUsed(response, "blueprints/index.html")

    def test_can_open_index_by_owner(self):
        # given
        self.client.force_login(self.user_owner)
        # when
        response = self.client.get("/blueprints/")
        # then
        self.assertTemplateUsed(response, "blueprints/index.html")

    def test_can_open_blueprint_modal(self):
        # given
        self.client.force_login(self.user_owner)
        # when
        response = self.client.get(
            f"/blueprints/modals/view_blueprint?blueprint_id={self.blueprint.pk}"
        )
        # then
        self.assertContains(response, self.blueprint.eve_type.name)

    def test_can_open_request_modal(self):
        # given
        user_request = Request.objects.create(
            blueprint=self.blueprint,
            runs=None,
            requesting_user=self.user_requestor,
            status=Request.STATUS_IN_PROGRESS,
        )
        self.client.force_login(self.user_owner)
        # when
        response = self.client.get(
            f"/blueprints/modals/view_request?request_id={user_request.pk}"
        )
        # then
        self.assertContains(response, self.blueprint.eve_type.name)


@patch(VIEWS_PATH + ".tasks.update_locations_for_owner")
@patch(VIEWS_PATH + ".tasks.update_blueprints_for_owner")
@patch(VIEWS_PATH + ".notify_admins")
@patch(VIEWS_PATH + ".messages")
class TestAddCorporationBlueprintOwner(TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        super().setUpClass()
        cls.factory = RequestFactory()
        load_eveuniverse()
        load_entities()
        load_locations()
        cls.user, _ = create_user_from_evecharacter(
            1001,
            permissions=[
                "blueprints.basic_access",
                "blueprints.add_corporate_blueprint_owner",
            ],
        )

    def _add_corporate_blueprint_owner(self, token=None, user=None):
        # given
        request = self.factory.get(reverse("blueprints:add_corporate_blueprint_owner"))
        if not user:
            user = self.user
        if not token:
            token = user.token_set.first()
        request.user = user
        request.token = token
        middleware = SessionMiddleware(Mock())
        middleware.process_request(request)
        orig_view = add_corporation_blueprint_owner.__wrapped__.__wrapped__.__wrapped__
        # when
        return orig_view(request, token)

    @patch(VIEWS_PATH + ".BLUEPRINTS_ADMIN_NOTIFICATIONS_ENABLED", True)
    def test_should_add_new_owner_and_notify_admins(
        self,
        mock_messages,
        mock_notify_admins,
        mock_update_blueprints_for_owner,
        mock_update_locations_for_owner,
    ):
        # when
        response = self._add_corporate_blueprint_owner()
        # then
        self.assertEqual(response.status_code, 302)
        self.assertEqual(response.url, reverse("blueprints:index"))
        self.assertTrue(mock_messages.info.called)
        self.assertTrue(mock_notify_admins.called)
        owner = Owner.objects.first()
        self.assertEqual(
            owner.corporation.corporation_id,
            self.user.profile.main_character.corporation_id,
        )
        self.assertTrue(mock_update_blueprints_for_owner.delay.called)
        self.assertTrue(mock_update_locations_for_owner.delay.called)

    @patch(VIEWS_PATH + ".BLUEPRINTS_ADMIN_NOTIFICATIONS_ENABLED", False)
    def test_should_add_new_owner_and_not_notify_admins(
        self,
        mock_messages,
        mock_notify_admins,
        mock_update_blueprints_for_owner,
        mock_update_locations_for_owner,
    ):
        # when
        response = self._add_corporate_blueprint_owner()
        # then
        self.assertEqual(response.status_code, 302)
        self.assertEqual(response.url, reverse("blueprints:index"))
        self.assertTrue(mock_messages.info.called)
        self.assertFalse(mock_notify_admins.called)
        owner = Owner.objects.first()
        self.assertEqual(
            owner.corporation.corporation_id,
            self.user.profile.main_character.corporation_id,
        )
        self.assertTrue(mock_update_blueprints_for_owner.delay.called)
        self.assertTrue(mock_update_locations_for_owner.delay.called)


@patch(VIEWS_PATH + ".tasks.update_locations_for_owner")
@patch(VIEWS_PATH + ".tasks.update_blueprints_for_owner")
@patch(VIEWS_PATH + ".notify_admins")
@patch(VIEWS_PATH + ".messages")
class TestAddPersonalBlueprintOwner(TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        super().setUpClass()
        cls.factory = RequestFactory()
        load_eveuniverse()
        load_entities()
        load_locations()
        cls.user, _ = create_user_from_evecharacter(
            1001,
            permissions=[
                "blueprints.basic_access",
                "blueprints.add_personal_blueprint_owner",
            ],
        )

    def _add_personal_blueprint_owner(self, token=None, user=None):
        # given
        request = self.factory.get(reverse("blueprints:add_personal_blueprint_owner"))
        if not user:
            user = self.user
        if not token:
            token = user.token_set.first()
        request.user = user
        request.token = token
        middleware = SessionMiddleware(Mock())
        middleware.process_request(request)
        orig_view = add_personal_blueprint_owner.__wrapped__.__wrapped__.__wrapped__
        # when
        return orig_view(request, token)

    @patch(VIEWS_PATH + ".BLUEPRINTS_ADMIN_NOTIFICATIONS_ENABLED", True)
    def test_should_add_new_owner_and_notify_admins(
        self,
        mock_messages,
        mock_notify_admins,
        mock_update_blueprints_for_owner,
        mock_update_locations_for_owner,
    ):
        # when
        response = self._add_personal_blueprint_owner()
        # then
        self.assertEqual(response.status_code, 302)
        self.assertEqual(response.url, reverse("blueprints:index"))
        self.assertTrue(mock_messages.info.called)
        self.assertTrue(mock_notify_admins.called)
        owner = Owner.objects.first()
        self.assertIsNone(owner.corporation)
        self.assertEqual(
            owner.character.character.character_id,
            self.user.profile.main_character.character_id,
        )
        self.assertTrue(mock_update_blueprints_for_owner.delay.called)
        self.assertTrue(mock_update_locations_for_owner.delay.called)
        _, kwargs = mock_notify_admins.call_args
        self.assertIn(owner.character.character.character_name, kwargs["title"])
        self.assertIn(owner.character.character.character_name, kwargs["message"])

    @patch(VIEWS_PATH + ".BLUEPRINTS_ADMIN_NOTIFICATIONS_ENABLED", False)
    def test_should_add_new_owner_and_not_notify_admins(
        self,
        mock_messages,
        mock_notify_admins,
        mock_update_blueprints_for_owner,
        mock_update_locations_for_owner,
    ):
        # when
        response = self._add_personal_blueprint_owner()
        # then
        self.assertEqual(response.status_code, 302)
        self.assertEqual(response.url, reverse("blueprints:index"))
        self.assertTrue(mock_messages.info.called)
        self.assertFalse(mock_notify_admins.called)
        owner = Owner.objects.first()
        self.assertIsNone(owner.corporation)
        self.assertEqual(
            owner.character.character.character_id,
            self.user.profile.main_character.character_id,
        )
        self.assertTrue(mock_update_blueprints_for_owner.delay.called)
        self.assertTrue(mock_update_locations_for_owner.delay.called)
