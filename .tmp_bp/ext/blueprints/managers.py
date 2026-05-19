"""Managers for Blueprints."""

# pylint: disable = missing-class-docstring

import datetime as dt
from typing import Any, Tuple

from bravado.exception import HTTPForbidden, HTTPUnauthorized

from django.contrib.auth.models import User
from django.db import models
from django.db.models import Case, Count, F, Q, Value, When
from django.db.models.functions import Concat
from django.utils.timezone import now
from esi.models import Token
from eveuniverse.models import EveEntity, EveSolarSystem, EveType

from allianceauth.eveonline.models import EveAllianceInfo, EveCorporationInfo
from allianceauth.services.hooks import get_extension_logger
from app_utils.esi import fetch_esi_status
from app_utils.logging import LoggerAddTag

from . import __title__
from .app_settings import BLUEPRINTS_LOCATION_STALE_HOURS
from .constants import EVE_TYPE_ID_SOLAR_SYSTEM
from .providers import esi

logger = LoggerAddTag(get_extension_logger(__name__), __title__)


class BlueprintQuerySet(models.QuerySet):
    def annotate_is_bpo(self) -> models.QuerySet:
        """Add is_bop Annotation to query."""
        return self.annotate(
            is_bpo=Case(
                When(runs=None, then=Value("yes")),
                default=Value("no"),
                output_field=models.CharField(),
            )
        )

    def annotate_owner_name(self) -> models.QuerySet:
        """Add owner_name Annotation to query."""
        return self.select_related(
            "owner__character__character", "owner__corporation"
        ).annotate(
            owner_name=Case(
                When(
                    owner__corporation=None,
                    then=F("owner__character__character__character_name"),
                ),
                default=F("owner__corporation__corporation_name"),
                output_field=models.CharField(),
            )
        )

    def annotate_location_name(self) -> models.QuerySet:
        """Annotate calculated location name field
        with parent locations up to 3 levels up.
        """
        return self.annotate(
            location_name=Case(
                When(~Q(location__name=""), then=F("location__name")),
                When(
                    ~Q(location__parent=None) & ~Q(location__parent__name=""),
                    then=F("location__parent__name"),
                ),
                When(
                    ~Q(location__parent=None)
                    & ~Q(location__parent__parent=None)
                    & ~Q(location__parent__parent__name=""),
                    then=F("location__parent__parent__name"),
                ),
                When(
                    ~Q(location__parent=None)
                    & ~Q(location__parent__parent=None)
                    & ~Q(location__parent__parent__parent=None)
                    & ~Q(location__parent__parent__parent__name=""),
                    then=F("location__parent__parent__parent__name"),
                ),
                default=Concat(
                    Value("Location #"), "location__id", output_field=models.CharField()
                ),
                output_field=models.CharField(),
            )
        )


class BlueprintManagerBase(models.Manager):
    def user_has_access(self, user: User) -> models.QuerySet:
        """Filter query to blueprints a given user has access to."""
        from .models import Owner

        corporation_ids = set(
            user.character_ownerships.select_related("character").values_list(
                "character__corporation_id", flat=True
            )
        )
        if user.has_perm("blueprints.view_alliance_blueprints"):
            alliance_ids = list(
                EveAllianceInfo.objects.filter(
                    evecorporationinfo__corporation_id__in=corporation_ids
                ).values_list("id", flat=True)
            )  # we use the django ID here to avoid a join later
            corporation_ids = corporation_ids | set(
                EveCorporationInfo.objects.filter(
                    alliance_id__in=alliance_ids
                ).values_list("corporation_id", flat=True)
            )

        personal_owner_ids = [
            owner.pk
            for owner in Owner.objects.filter(
                corporation__isnull=True, character__isnull=False
            )
            if owner.eve_character_strict.corporation_id in corporation_ids
        ]
        blueprints_query = self.filter(
            Q(owner__corporation__corporation_id__in=corporation_ids)
            | Q(owner__pk__in=personal_owner_ids)
        ).select_related(
            "eve_type",
            "location",
            "industryjob",
            "owner",
            "owner__corporation",
            "owner__character",
            "location",
            "location__eve_solar_system",
            "location__eve_type",
        )
        return blueprints_query


BlueprintManager = BlueprintManagerBase.from_queryset(BlueprintQuerySet)


class LocationQuerySet(models.QuerySet):
    def annotate_blueprint_count(self) -> models.QuerySet:
        """Add annotate with count of blueprints."""
        return self.annotate(blueprint_count=Count("blueprints"))


class LocationManagerBase(models.Manager):
    """A manager for the Location model.

    We recommend preferring the "async" variants, because it includes protection
    against exceeding the ESI error limit due to characters no longer having access
    to structures within their assets, contracts, etc.

    The async methods will first create an empty location and then try to
    update that empty location asynchronously from ESI.
    Updates might be delayed if the error limit is reached.

    The async method can also be used safely in mass updates, where the same
    unauthorized update might be requested multiple times.
    Additional requests for the same location will be ignored within a grace period.
    """

    _UPDATE_EMPTY_GRACE_MINUTES = 5

    def get_or_create_esi(self, id: int, token: Token) -> Tuple[Any, bool]:
        """Get or create location object with data fetched from ESI.

        Stale locations will always be updated.
        Empty locations will always be updated after grace period as passed
        """
        return self._get_or_create_esi(id=id, token=token, update_async=False)

    def get_or_create_esi_async(self, id: int, token: Token) -> Tuple[Any, bool]:
        """Get or create location object with data fetched from ESI asynchronous."""
        return self._get_or_create_esi(id=id, token=token, update_async=True)

    def _get_or_create_esi(
        self, id: int, token: Token, update_async: bool = True
    ) -> Tuple[Any, bool]:
        id = int(id)
        empty_threshold = now() - dt.timedelta(minutes=self._UPDATE_EMPTY_GRACE_MINUTES)
        stale_threshold = now() - dt.timedelta(hours=BLUEPRINTS_LOCATION_STALE_HOURS)
        try:
            location = (
                self.exclude(
                    eve_type__isnull=True,
                    eve_solar_system__isnull=True,
                    updated_at__lt=empty_threshold,
                )
                .exclude(updated_at__lt=stale_threshold)
                .get(id=id)
            )
            created = False
        except self.model.DoesNotExist:
            if update_async:
                location, created = self.update_or_create_esi_async(id=id, token=token)
            else:
                location, created = self.update_or_create_esi(id=id, token=token)

        return location, created

    def update_or_create_esi_async(self, id: int, token: Token) -> Tuple[Any, bool]:
        """Update or create location object with data fetched from ESI asynchronous."""
        return self._update_or_create_esi(id=id, token=token, update_async=True)

    def update_or_create_esi(self, id: int, token: Token) -> Tuple[Any, bool]:
        """Update or create location object with data fetched from ESI synchronous.

        The preferred method to use is: `update_or_create_esi_async()`,
        since it protects against exceeding the ESI error limit and which can happen
        a lot due to users not having authorization to access a structure.
        """
        return self._update_or_create_esi(id=id, token=token, update_async=False)

    def _update_or_create_esi(
        self, id: int, token: Token, update_async: bool = True
    ) -> Tuple[Any, bool]:
        id = int(id)
        if self.model.is_solar_system_id(id):
            eve_solar_system, _ = EveSolarSystem.objects.get_or_create_esi(id=id)
            eve_type, _ = EveType.objects.get_or_create_esi(id=EVE_TYPE_ID_SOLAR_SYSTEM)
            location, created = self.update_or_create(
                id=id,
                defaults={
                    "name": eve_solar_system.name,
                    "eve_solar_system": eve_solar_system,
                    "eve_type": eve_type,
                },
            )
        elif self.model.is_station_id(id):
            logger.info("%s: Fetching station from ESI", id)
            station = esi.client.Universe.get_universe_stations_station_id(
                station_id=id
            ).results()
            location, created = self._station_update_or_create_dict(
                id=id, station=station
            )

        else:  # structure or random asset
            if update_async:
                location, created = self._structure_update_or_create_esi_async(
                    id=id, token=token
                )
            else:
                location, created = self.structure_update_or_create_esi(
                    id=id, token=token
                )

        return location, created

    def _station_update_or_create_dict(
        self, id: int, station: dict
    ) -> Tuple[Any, bool]:
        if station.get("system_id"):
            eve_solar_system, _ = EveSolarSystem.objects.get_or_create_esi(
                id=station.get("system_id")
            )
        else:
            eve_solar_system = None

        if station.get("type_id"):
            eve_type, _ = EveType.objects.get_or_create_esi(id=station.get("type_id"))
        else:
            eve_type = None

        if station.get("owner"):
            owner, _ = EveEntity.objects.get_or_create_esi(id=station.get("owner"))
        else:
            owner = None

        return self.update_or_create(
            id=id,
            defaults={
                "name": station.get("name", ""),
                "eve_solar_system": eve_solar_system,
                "eve_type": eve_type,
                "owner": owner,
            },
        )

    def _structure_update_or_create_esi_async(self, id: int, token: Token):
        from .tasks import DEFAULT_TASK_PRIORITY
        from .tasks import update_structure_esi as task_update_structure_esi

        id = int(id)
        location, created = self.get_or_create(id=id)
        task_update_structure_esi.apply_async(
            kwargs={"structure_id": id, "token_pk": token.pk},
            priority=DEFAULT_TASK_PRIORITY,
        )
        return location, created

    def structure_update_or_create_esi(self, id: int, token: Token) -> Tuple[Any, bool]:
        """Update or creates structure from ESI"""
        fetch_esi_status().raise_for_status()
        try:
            structure_data = esi.client.Universe.get_universe_structures_structure_id(
                structure_id=id, token=token.valid_access_token()
            ).results()
        except (HTTPUnauthorized, HTTPForbidden) as http_error:
            logger.warning(
                "%s: No access to structure #%s: %s",
                token.character_name,
                id,
                http_error,
            )
            return self.get_or_create(id=id)

        return self._structure_update_or_create_dict(id=id, structure=structure_data)

    def _structure_update_or_create_dict(
        self, id: int, structure: dict
    ) -> Tuple[Any, bool]:
        """creates a new Location object from a structure dict"""
        if structure.get("solar_system_id"):
            eve_solar_system, _ = EveSolarSystem.objects.get_or_create_esi(
                id=structure.get("solar_system_id")
            )
        else:
            eve_solar_system = None

        if structure.get("type_id"):
            eve_type, _ = EveType.objects.get_or_create_esi(id=structure.get("type_id"))
        else:
            eve_type = None

        if structure.get("owner_id"):
            owner, _ = EveEntity.objects.get_or_create_esi(id=structure.get("owner_id"))
        else:
            owner = None

        return self.update_or_create(
            id=id,
            defaults={
                "name": structure.get("name", ""),
                "eve_solar_system": eve_solar_system,
                "eve_type": eve_type,
                "owner": owner,
            },
        )


LocationManager = LocationManagerBase.from_queryset(LocationQuerySet)


class OwnerQuerySet(models.QuerySet):
    def annotate_blueprint_count(self) -> models.QuerySet:
        """Add annotate with count of blueprints."""
        return self.annotate(blueprint_count=Count("blueprints"))


class OwnerManagerBase(models.Manager):
    pass


OwnerManager = OwnerManagerBase.from_queryset(OwnerQuerySet)


class RequestQuerySet(models.QuerySet):
    def requests_fulfillable_by_user(
        self, user: User, character_ownerships=None
    ) -> models.QuerySet:
        """Add filter to only include requests which can be fulfilled by the given user."""
        if not character_ownerships:
            character_ownerships = user.character_ownerships.select_related("character")
        corporation_ids = {
            ownership.character.corporation_id for ownership in character_ownerships
        }
        character_ownership_pks = {ownership.pk for ownership in character_ownerships}
        request_query = self.select_related(
            "blueprint__owner", "blueprint__owner__corporation"
        ).filter(
            (
                Q(blueprint__owner__corporation__corporation_id__in=corporation_ids)
                | Q(blueprint__owner__character__pk__in=character_ownership_pks)
            )
            & Q(closed_at=None)
            & Q(status=self.model.STATUS_OPEN)
        )
        return request_query

    def requests_being_fulfilled_by_user(
        self, user: User, character_ownerships=None
    ) -> models.QuerySet:
        """Add filter to only include requests being fulfilled by the given user."""
        if not character_ownerships:
            character_ownerships = user.character_ownerships.select_related("character")
        corporation_ids = {
            ownership.character.corporation_id for ownership in character_ownerships
        }
        character_ownership_pks = {ownership.pk for ownership in character_ownerships}
        request_query = self.select_related(
            "blueprint__owner", "blueprint__owner__corporation"
        ).filter(
            (
                Q(blueprint__owner__corporation__corporation_id__in=corporation_ids)
                | Q(blueprint__owner__character__pk__in=character_ownership_pks)
            )
            & Q(closed_at=None)
            & Q(status=self.model.STATUS_IN_PROGRESS)
            & Q(fulfulling_user=user)
        )
        return request_query


class RequestManagerBase(models.Manager):
    def select_related_default(self) -> models.QuerySet:
        """Add default select related to this query."""
        return self.select_related(
            "blueprint",
            "blueprint__owner",
            "blueprint__eve_type",
            "requesting_user__profile__main_character",
        )

    def open_requests_total_count(self, user: User) -> int:
        """Return total count of open requests for user"""
        character_ownerships = user.character_ownerships.select_related("character")
        return (
            self.all().requests_fulfillable_by_user(user, character_ownerships).count()
            + self.all()
            .requests_being_fulfilled_by_user(user, character_ownerships)
            .count()
        )


RequestManager = RequestManagerBase.from_queryset(RequestQuerySet)
