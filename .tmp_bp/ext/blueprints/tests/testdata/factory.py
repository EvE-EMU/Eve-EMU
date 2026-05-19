from typing import Generic, TypeVar

import factory
import factory.fuzzy

from eveuniverse.models import EveSolarSystem, EveType

from app_utils.testdata_factories import UserMainFactory

from blueprints import constants
from blueprints.models import Blueprint, Location, Owner

T = TypeVar("T")

faker = factory.faker.faker.Faker()


class BaseMetaFactory(Generic[T], factory.base.FactoryMetaClass):
    def __call__(cls, *args, **kwargs) -> T:
        return super().__call__(*args, **kwargs)


class UserMainDefaultFactory(UserMainFactory):
    main_character__scopes = [
        "esi-universe.read_structures.v1",
        "esi-assets.read_assets.v1",
        "esi-characters.read_blueprints.v1",
    ]
    permissions__ = [
        "blueprints.basic_access",
        "blueprints.add_personal_blueprint_owner",
    ]


class LocationStationFactory(
    factory.django.DjangoModelFactory, metaclass=BaseMetaFactory[Location]
):
    class Meta:
        model = Location

    id = factory.Sequence(lambda o: o + 60_000_000)
    name = factory.Faker("city")

    @factory.lazy_attribute
    def eve_solar_system(self):
        return EveSolarSystem.objects.order_by("?").first()

    @factory.lazy_attribute
    def eve_type(self):
        return (
            EveType.objects.filter(
                eve_group__eve_category_id=constants.EVE_CATEGORY_ID_STATION,
                published=True,
            )
            .order_by("?")
            .first()
        )


class OwnerFactory(factory.django.DjangoModelFactory, metaclass=BaseMetaFactory[Owner]):
    class Meta:
        model = Owner

    @factory.lazy_attribute
    def character(self):
        user = UserMainDefaultFactory()
        return user.profile.main_character.character_ownership


class BlueprintFactory(
    factory.django.DjangoModelFactory, metaclass=BaseMetaFactory[Blueprint]
):
    class Meta:
        model = Blueprint

    item_id = factory.Sequence(lambda o: o + 100_000_000)
    owner = factory.SubFactory(OwnerFactory)
    location = factory.SubFactory(LocationStationFactory)
    location_flag = "Hangar"
    quantity = 1
    runs = None
    material_efficiency = 10
    time_efficiency = 20

    @factory.lazy_attribute
    def eve_type(self):
        return (
            EveType.objects.filter(
                eve_group__eve_category_id=constants.EVE_CATEGORY_ID_BLUEPRINT,
                published=True,
            )
            .order_by("?")
            .first()
        )
