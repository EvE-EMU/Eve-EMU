"""Tasks for Blueprints."""

from celery import Task, shared_task

from esi.models import Token

from allianceauth.services.hooks import get_extension_logger
from allianceauth.services.tasks import QueueOnce
from app_utils.esi import retry_task_on_esi_error_and_offline
from app_utils.logging import LoggerAddTag

from . import __title__
from .app_settings import BLUEPRINTS_TASKS_TIME_LIMIT
from .models import Location, Owner

DEFAULT_TASK_PRIORITY = 6
logger = LoggerAddTag(get_extension_logger(__name__), __title__)


@shared_task(time_limit=BLUEPRINTS_TASKS_TIME_LIMIT)
def update_all_blueprints():
    """Update all blueprints."""
    for owner in Owner.objects.filter(is_active=True):
        update_blueprints_for_owner.apply_async(
            kwargs={"owner_pk": owner.pk}, priority=DEFAULT_TASK_PRIORITY
        )


@shared_task(
    bind=True,
    base=QueueOnce,
    once={"keys": ["owner_pk"], "graceful": True},
    time_limit=BLUEPRINTS_TASKS_TIME_LIMIT,
)
def update_blueprints_for_owner(self: Task, owner_pk: int):
    """Fetch all blueprints for an owner from ESI."""
    owner = Owner.objects.get(pk=owner_pk)
    with retry_task_on_esi_error_and_offline(self):
        owner.update_blueprints_esi()


@shared_task(time_limit=BLUEPRINTS_TASKS_TIME_LIMIT)
def update_all_industry_jobs():
    """Update all industry jobs."""
    for owner in Owner.objects.filter(is_active=True):
        update_industry_jobs_for_owner.apply_async(
            kwargs={"owner_pk": owner.pk}, priority=DEFAULT_TASK_PRIORITY
        )


@shared_task(
    bind=True,
    base=QueueOnce,
    once={"keys": ["owner_pk"], "graceful": True},
    time_limit=BLUEPRINTS_TASKS_TIME_LIMIT,
)
def update_industry_jobs_for_owner(self: Task, owner_pk: int):
    """Fetch all industry jobs for an owner from ESI."""
    owner = Owner.objects.get(pk=owner_pk)
    with retry_task_on_esi_error_and_offline(self):
        owner.update_industry_jobs_esi()


@shared_task(time_limit=BLUEPRINTS_TASKS_TIME_LIMIT)
def update_all_locations():
    """Update all locations."""
    for owner in Owner.objects.filter(is_active=True):
        update_locations_for_owner.apply_async(
            kwargs={"owner_pk": owner.pk}, priority=DEFAULT_TASK_PRIORITY
        )


@shared_task(
    bind=True,
    base=QueueOnce,
    once={"keys": ["owner_pk"], "graceful": True},
    time_limit=BLUEPRINTS_TASKS_TIME_LIMIT,
)
def update_locations_for_owner(self: Task, owner_pk: int):
    """Fetch all blueprints for an owner from ESI."""
    owner = Owner.objects.get(pk=owner_pk)
    with retry_task_on_esi_error_and_offline(self):
        owner.update_locations_esi()


@shared_task(
    bind=True,
    max_retries=None,
    base=QueueOnce,
    once={"keys": ["structure_id"], "graceful": True},
    time_limit=BLUEPRINTS_TASKS_TIME_LIMIT,
)
def update_structure_esi(self, structure_id: int, token_pk: int):
    """Update a structure object from ESI."""
    token = Token.objects.get(pk=token_pk)
    with retry_task_on_esi_error_and_offline(self):
        Location.objects.structure_update_or_create_esi(id=structure_id, token=token)
