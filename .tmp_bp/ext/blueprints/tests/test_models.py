import datetime as dt
from unittest.mock import patch

from django.utils.dateparse import parse_datetime
from django.utils.timezone import now
from esi.errors import TokenError, TokenExpiredError
from esi.models import Token
from eveuniverse.models import EveType

from allianceauth.eveonline.models import EveCharacter, EveCorporationInfo
from allianceauth.tests.auth_utils import AuthUtils
from app_utils.testing import NoSocketsTestCase

from blueprints.models import Blueprint, Location, Owner, Request

from . import add_character_to_user, create_owner, create_user_from_evecharacter
from .testdata.esi_client_stub import esi_client_stub
from .testdata.factory import BlueprintFactory, LocationStationFactory, OwnerFactory
from .testdata.load_entities import load_entities
from .testdata.load_eveuniverse import load_eveuniverse
from .testdata.load_locations import load_locations

MANAGERS_PATH = "blueprints.managers"
MODELS_PATH = "blueprints.models"


class TestBlueprintsBase(NoSocketsTestCase):
    @classmethod
    def setUpClass(cls) -> None:
        super().setUpClass()
        load_entities()
        load_eveuniverse()
        load_locations()


class TestBlueprintQuerySet(TestBlueprintsBase):
    @classmethod
    def setUpClass(cls) -> None:
        super().setUpClass()
        # given
        cls.owner_1001 = create_owner(character_id=1001, corporation_id=None)
        Blueprint.objects.create(
            location=Location.objects.get(id=60003760),
            eve_type=EveType.objects.get(id=33519),
            owner=cls.owner_1001,
            runs=10,
            location_flag="AssetSafety",
            material_efficiency=10,
            time_efficiency=30,
            item_id=1,
        )
        cls.owner_1002 = create_owner(character_id=1002, corporation_id=2001)
        Blueprint.objects.create(
            location=Location.objects.get(id=1000000000001),
            eve_type=EveType.objects.get(id=33519),
            owner=cls.owner_1002,
            location_flag="AssetSafety",
            material_efficiency=20,
            time_efficiency=40,
            item_id=2,
        )

    def test_should_annotate_is_bpo(self):
        # when
        result = Blueprint.objects.all().annotate_is_bpo().values()
        # then
        obj = result[0]
        self.assertEqual(obj["item_id"], 1)
        self.assertEqual(obj["is_bpo"], "no")
        obj = result[1]
        self.assertEqual(obj["item_id"], 2)
        self.assertEqual(obj["is_bpo"], "yes")

    def test_should_annotate_owner_name(self):
        # when
        result = Blueprint.objects.all().annotate_owner_name().values()
        # then
        obj = result[0]
        self.assertEqual(obj["item_id"], 1)
        self.assertEqual(obj["owner_name"], "Bruce Wayne")
        obj = result[1]
        self.assertEqual(obj["item_id"], 2)
        self.assertEqual(obj["owner_name"], "Wayne Technologies")


class TestBlueprintManagerUserHasAccess(TestBlueprintsBase):
    @classmethod
    def setUpClass(cls) -> None:
        super().setUpClass()
        # given
        cls.owner_1002 = create_owner(character_id=1002, corporation_id=2001)
        Blueprint.objects.create(
            location=Location.objects.get(id=60003760),
            eve_type=EveType.objects.get(id=33519),
            owner=cls.owner_1002,
            location_flag="AssetSafety",
            material_efficiency=10,
            time_efficiency=30,
            item_id=2,
        )
        cls.owner_1003 = create_owner(character_id=1003, corporation_id=2002)
        Blueprint.objects.create(
            location=Location.objects.get(id=60003760),
            eve_type=EveType.objects.get(id=33519),
            owner=cls.owner_1003,
            location_flag="AssetSafety",
            material_efficiency=10,
            time_efficiency=30,
            item_id=3,
        )
        cls.owner_1101 = create_owner(character_id=1101, corporation_id=2101)
        Blueprint.objects.create(
            location=Location.objects.get(id=60003760),
            eve_type=EveType.objects.get(id=33519),
            owner=cls.owner_1101,
            location_flag="AssetSafety",
            material_efficiency=10,
            time_efficiency=30,
            item_id=4,
        )
        cls.owner_1102 = create_owner(character_id=1102, corporation_id=2102)
        Blueprint.objects.create(
            location=Location.objects.get(id=60003760),
            eve_type=EveType.objects.get(id=33519),
            owner=cls.owner_1102,
            location_flag="AssetSafety",
            material_efficiency=10,
            time_efficiency=30,
            item_id=5,
        )
        cls.owner_1004 = create_owner(character_id=1004, corporation_id=None)
        Blueprint.objects.create(
            location=Location.objects.get(id=60003760),
            eve_type=EveType.objects.get(id=33519),
            owner=cls.owner_1004,
            location_flag="AssetSafety",
            material_efficiency=10,
            time_efficiency=30,
            item_id=6,
        )

    def setUp(self) -> None:
        # given
        self.owner_1001 = create_owner(character_id=1001, corporation_id=None)
        self.user = self.owner_1001.character.user
        add_character_to_user(self.user, EveCharacter.objects.get(character_id=1103))
        Blueprint.objects.create(
            location=Location.objects.get(id=60003760),
            eve_type=EveType.objects.get(id=33519),
            owner=self.owner_1001,
            location_flag="AssetSafety",
            material_efficiency=10,
            time_efficiency=30,
            item_id=1,
        )

    def test_should_return_personal_and_corporation_and_alt_corporation(self):
        # when
        qs = Blueprint.objects.user_has_access(self.user)
        # then
        self.assertSetEqual(set(qs.values_list("item_id", flat=True)), {1, 2, 5})

    def test_should_return_personal_and_corporation_and_alt_corporation_and_alliance(
        self,
    ):
        # given
        self.user = AuthUtils.add_permission_to_user_by_name(
            "blueprints.view_alliance_blueprints", self.user
        )
        # when
        qs = Blueprint.objects.user_has_access(self.user)
        # then
        self.assertSetEqual(set(qs.values_list("item_id", flat=True)), {1, 2, 3, 5, 6})


class TestBlueprintManagerAnnotateLocationName(NoSocketsTestCase):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        load_eveuniverse()
        cls.owner = OwnerFactory()

    def test_should_return_name(self):
        # given
        location = LocationStationFactory(name="Alpha")
        BlueprintFactory(owner=self.owner, location=location)
        # when
        qs = Blueprint.objects.annotate_location_name()
        # then
        obj = qs.first()
        self.assertEqual(obj.location_name, "Alpha")

    def test_should_return_parent_name(self):
        # given
        parent_location = LocationStationFactory(name="Parent")
        child_location = LocationStationFactory(name="", parent=parent_location)
        BlueprintFactory(owner=self.owner, location=child_location)
        # when
        qs = Blueprint.objects.annotate_location_name()
        # then
        obj = qs.first()
        self.assertEqual(obj.location_name, "Parent")

    def test_should_return_generic_name(self):
        # given
        location = LocationStationFactory(name="")
        BlueprintFactory(owner=self.owner, location=location)
        # when
        qs = Blueprint.objects.annotate_location_name()
        # then
        obj = qs.first()
        self.assertEqual(obj.location_name, f"Location #{location.id}")

    def test_should_return_parent_parent_name(self):
        # given
        parent_location = LocationStationFactory(name="Parent")
        child_location = LocationStationFactory(name="", parent=parent_location)
        child_child_location = LocationStationFactory(name="", parent=child_location)
        BlueprintFactory(owner=self.owner, location=child_child_location)
        # when
        qs = Blueprint.objects.annotate_location_name()
        # then
        obj = qs.first()
        self.assertEqual(obj.location_name, "Parent")

    def test_should_return_parent_parent_parent_name(self):
        # given
        parent_location = LocationStationFactory(name="Parent")
        child_location = LocationStationFactory(name="", parent=parent_location)
        child_child_location = LocationStationFactory(name="", parent=child_location)
        child_child_child_location = LocationStationFactory(
            name="", parent=child_child_location
        )
        BlueprintFactory(owner=self.owner, location=child_child_child_location)
        # when
        qs = Blueprint.objects.annotate_location_name()
        # then
        obj = qs.first()
        self.assertEqual(obj.location_name, "Parent")

    def test_should_return_first_parent_with_name_with_4_nodes(self):
        # given
        parent_location = LocationStationFactory(name="Parent")
        child_location = LocationStationFactory(name="Child", parent=parent_location)
        child_child_location = LocationStationFactory(name="", parent=child_location)
        child_child_child_location = LocationStationFactory(
            name="", parent=child_child_location
        )
        BlueprintFactory(owner=self.owner, location=child_child_child_location)
        # when
        qs = Blueprint.objects.annotate_location_name()
        # then
        obj = qs.first()
        self.assertEqual(obj.location_name, "Child")

    def test_should_return_first_parent_with_name_with_3_nodes(self):
        # given
        parent_location = LocationStationFactory(name="Parent")
        child_location = LocationStationFactory(name="Child", parent=parent_location)
        child_child_location = LocationStationFactory(name="", parent=child_location)
        BlueprintFactory(owner=self.owner, location=child_child_location)
        # when
        qs = Blueprint.objects.annotate_location_name()
        # then
        obj = qs.first()
        self.assertEqual(obj.location_name, "Child")


@patch(MODELS_PATH + ".esi")
@patch(MANAGERS_PATH + ".esi")
class TestCorporateOwner(NoSocketsTestCase):
    @classmethod
    def setUpClass(cls) -> None:
        super().setUpClass()
        load_entities()
        load_eveuniverse()
        load_locations()

    def setUp(self) -> None:
        self.owner = create_owner(character_id=1101, corporation_id=2101)

    def test_should_return_corporation_name_for_owner(
        self, mock_esi_managers, mock_esi_models
    ):
        # when
        result = str(self.owner)
        # then
        self.assertEqual(result, "Lexcorp")

    def test_should_return_corporation_name_for_owner_with_no_character(
        self, mock_esi_managers, mock_esi_models
    ):
        # given
        owner = Owner.objects.create(
            corporation=EveCorporationInfo.objects.get(corporation_id=2001)
        )
        # when
        result = str(owner)
        # then
        self.assertEqual(result, "Wayne Technologies")

    def test_should_return_empty_string_for_empty_owner(
        self, mock_esi_managers, mock_esi_models
    ):
        # given
        owner = Owner.objects.create()
        # when
        result = str(owner)
        # then
        self.assertEqual(result, "")

    def test_update_locations_esi(self, mock_esi_managers, mock_esi_models):
        mock_esi_managers.client = esi_client_stub
        mock_esi_models.client = esi_client_stub

        self.owner.update_locations_esi()

        self.assertEqual(
            Location.objects.get(id=1100000000001).parent,
            Location.objects.get(id=60003760),
        )

    def test_update_blueprints_esi(self, mock_esi_managers, mock_esi_models):
        mock_esi_managers.client = esi_client_stub
        mock_esi_models.client = esi_client_stub
        self.owner.update_blueprints_esi()
        self.assertEqual(Blueprint.objects.filter(eve_type_id=33519).count(), 1)

    def test_should_update_industry_jobs_esi(self, mock_esi_managers, mock_esi_models):
        # given

        mock_esi_managers.client = esi_client_stub
        mock_esi_models.client = esi_client_stub
        self.owner.update_blueprints_esi()
        # when
        self.owner.update_industry_jobs_esi()
        # then
        self.assertEqual(self.owner.jobs.count(), 1)
        obj = self.owner.jobs.first()
        self.assertEqual(obj.id, 100000002)
        self.assertEqual(obj.activity, 5)
        self.assertEqual(obj.location_id, 1000000000001)
        self.assertEqual(obj.installer, EveCharacter.objects.get(character_id=1001))
        self.assertEqual(obj.runs, 1)
        self.assertEqual(obj.start_date, parse_datetime("2020-12-21T23:37:14Z"))
        self.assertEqual(obj.status, "active")


class TestLocationNamePlus(NoSocketsTestCase):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        load_eveuniverse()

    def test_should_return_name(self):
        # given
        location = LocationStationFactory(name="Alpha")
        # when/then
        self.assertEqual(location.full_qualified_name(), "Alpha")

    def test_should_return_parent_name(self):
        # given
        parent_location = LocationStationFactory(name="Parent")
        location = LocationStationFactory(name="Child", parent=parent_location)
        # when/then
        self.assertEqual(location.full_qualified_name(), "Parent - Child")

    def test_should_return_generic_name(self):
        # given
        location = LocationStationFactory(name="")
        # when/then
        self.assertEqual(location.full_qualified_name(), f"Location #{location.id}")

    def test_should_return_parent_parent_parent_name(self):
        # given
        parent_location = LocationStationFactory(name="Parent")
        child_location = LocationStationFactory(name="Child 1", parent=parent_location)
        child_child_location = LocationStationFactory(
            name="Child 2", parent=child_location
        )
        location = LocationStationFactory(name="Child 3", parent=child_child_location)
        # when/then
        self.assertEqual(
            location.full_qualified_name(), "Parent - Child 1 - Child 2 - Child 3"
        )


class TestOwnerValidToken(NoSocketsTestCase):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.owner = OwnerFactory()

    def test_should_return_valid_token(self):
        # when
        result = self.owner.valid_token(["esi-characters.read_blueprints.v1"])
        # then
        self.assertIsInstance(result, Token)

    def test_should_raise_error_when_no_token_with_requested_scope_found(self):
        # when/then
        with self.assertRaises(TokenError):
            self.owner.valid_token(["unknown-scope"])

    @patch(MODELS_PATH + ".Token.objects.filter")
    def test_should_raise_error_when_token_has_issue(self, mock):
        # given
        mock.side_effect = TokenExpiredError
        # when/then
        with self.assertRaises(TokenExpiredError):
            self.owner.valid_token(["esi-characters.read_blueprints.v1"])


@patch(MODELS_PATH + ".esi")
@patch(MANAGERS_PATH + ".esi")
class TestPersonalOwner(NoSocketsTestCase):
    @classmethod
    def setUpClass(cls) -> None:
        super().setUpClass()
        load_entities()
        load_eveuniverse()
        load_locations()

    def setUp(self) -> None:
        self.owner = create_owner(character_id=1101, corporation_id=None)

    def test_update_locations_esi(self, mock_esi_managers, mock_esi_models):
        mock_esi_managers.client = esi_client_stub
        mock_esi_models.client = esi_client_stub

        self.owner.update_locations_esi()

        self.assertEqual(
            Location.objects.get(id=1100000000001).parent,
            Location.objects.get(id=60003760),
        )

    def test_update_blueprints_esi(self, mock_esi_managers, mock_esi_models):
        mock_esi_managers.client = esi_client_stub
        mock_esi_models.client = esi_client_stub
        self.owner.update_blueprints_esi()
        self.assertEqual(Blueprint.objects.filter(eve_type_id=33519).count(), 1)

    def test_should_update_industry_jobs_esi(self, mock_esi_managers, mock_esi_models):
        # given

        mock_esi_managers.client = esi_client_stub
        mock_esi_models.client = esi_client_stub
        self.owner.update_blueprints_esi()
        # when
        self.owner.update_industry_jobs_esi()
        # then
        self.assertEqual(self.owner.jobs.count(), 1)
        obj = self.owner.jobs.first()
        self.assertEqual(obj.id, 100000001)
        self.assertEqual(obj.activity, 5)
        self.assertEqual(obj.location_id, 1000000000001)
        self.assertEqual(obj.installer, EveCharacter.objects.get(character_id=1001))
        self.assertEqual(obj.runs, 1)
        self.assertEqual(obj.start_date, parse_datetime("2020-12-21T23:37:14Z"))
        self.assertEqual(obj.status, "active")


class TestRequests(TestBlueprintsBase):
    @classmethod
    def setUpClass(cls) -> None:
        super().setUpClass()
        # given
        cls.user_1002, _ = create_user_from_evecharacter(1002)
        cls.owner_1001 = create_owner(character_id=1001, corporation_id=2001)
        cls.user_1001 = cls.owner_1001.character.user
        cls.bp_1 = Blueprint.objects.create(
            location=Location.objects.get(id=60003760),
            eve_type=EveType.objects.get(id=33519),
            owner=cls.owner_1001,
            location_flag="AssetSafety",
            material_efficiency=10,
            time_efficiency=30,
            item_id=2,
        )
        cls.owner_1101 = create_owner(character_id=1101, corporation_id=2101)
        cls.bp_2 = Blueprint.objects.create(
            location=Location.objects.get(id=60003760),
            eve_type=EveType.objects.get(id=33519),
            owner=cls.owner_1101,
            location_flag="AssetSafety",
            material_efficiency=10,
            time_efficiency=30,
            item_id=3,
        )

    def test_should_strings(self):
        # given
        req_1 = Request.objects.create(
            blueprint=self.bp_1,
            requesting_user=self.user_1002,
            status=Request.STATUS_OPEN,
        )
        # when/then
        self.assertTrue(str(req_1))
        self.assertTrue(repr(req_1))

    def test_should_return_fulfillable_requests(self):
        # given
        req_1 = Request.objects.create(
            blueprint=self.bp_1,
            requesting_user=self.user_1002,
            status=Request.STATUS_OPEN,
        )
        Request.objects.create(
            blueprint=self.bp_1,
            requesting_user=self.user_1002,
            status=Request.STATUS_FULFILLED,
        )
        Request.objects.create(
            blueprint=self.bp_2,
            requesting_user=self.user_1002,
            status=Request.STATUS_OPEN,
        )
        Request.objects.create(
            blueprint=self.bp_1,
            requesting_user=self.user_1002,
            status=Request.STATUS_OPEN,
            closed_at=now() - dt.timedelta(days=1),
        )
        # when
        result = Request.objects.all().requests_fulfillable_by_user(self.user_1001)
        # then
        result_pks = set(result.values_list("pk", flat=True))
        self.assertSetEqual(result_pks, {req_1.pk})

    def test_should_return_requests_being_fulfilled(self):
        # given
        req_1 = Request.objects.create(
            blueprint=self.bp_1,
            requesting_user=self.user_1002,
            status=Request.STATUS_IN_PROGRESS,
            fulfulling_user=self.user_1001,
        )
        Request.objects.create(
            blueprint=self.bp_1,
            requesting_user=self.user_1002,
            status=Request.STATUS_OPEN,
        )
        Request.objects.create(
            blueprint=self.bp_1,
            requesting_user=self.user_1002,
            status=Request.STATUS_FULFILLED,
        )
        Request.objects.create(
            blueprint=self.bp_2,
            requesting_user=self.user_1002,
            status=Request.STATUS_OPEN,
        )
        Request.objects.create(
            blueprint=self.bp_1,
            requesting_user=self.user_1002,
            status=Request.STATUS_IN_PROGRESS,
            fulfulling_user=self.user_1001,
            closed_at=now() - dt.timedelta(days=1),
        )
        # when
        result = Request.objects.all().requests_being_fulfilled_by_user(self.user_1001)
        # then
        result_pks = set(result.values_list("pk", flat=True))
        self.assertSetEqual(result_pks, {req_1.pk})

    def test_should_return_open_requests_total_count(self):
        # given
        Request.objects.create(
            blueprint=self.bp_1,
            requesting_user=self.user_1002,
            status=Request.STATUS_IN_PROGRESS,
            fulfulling_user=self.user_1001,
        )
        Request.objects.create(
            blueprint=self.bp_1,
            requesting_user=self.user_1002,
            status=Request.STATUS_OPEN,
        )
        Request.objects.create(
            blueprint=self.bp_1,
            requesting_user=self.user_1002,
            status=Request.STATUS_FULFILLED,
        )
        Request.objects.create(
            blueprint=self.bp_2,
            requesting_user=self.user_1002,
            status=Request.STATUS_OPEN,
        )
        Request.objects.create(
            blueprint=self.bp_1,
            requesting_user=self.user_1002,
            status=Request.STATUS_IN_PROGRESS,
            fulfulling_user=self.user_1001,
            closed_at=now() - dt.timedelta(days=1),
        )
        # when
        result = Request.objects.open_requests_total_count(self.user_1001)
        # then
        self.assertEqual(result, 2)
