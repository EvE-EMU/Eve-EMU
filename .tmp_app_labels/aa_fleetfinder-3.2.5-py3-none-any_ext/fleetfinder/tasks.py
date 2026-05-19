"""
Tasks
"""

# Standard Library
from collections.abc import Iterable
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import timedelta

# Third Party
from celery import shared_task

# Django
from django.utils import timezone

# Alliance Auth
from allianceauth.services.hooks import get_extension_logger
from allianceauth.services.tasks import QueueOnce
from esi.exceptions import HTTPClientError
from esi.models import Token

# AA Fleet Finder
from fleetfinder import __title__
from fleetfinder.handler import esi_handler
from fleetfinder.models import Fleet
from fleetfinder.providers import AppLogger, esi

logger = AppLogger(my_logger=get_extension_logger(name=__name__), prefix=__title__)


ESI_ERROR_LIMIT = 50
ESI_TIMEOUT_ONCE_ERROR_LIMIT_REACHED = 60
ESI_MAX_RETRIES = 3
ESI_MAX_ERROR_COUNT = 3
ESI_ERROR_GRACE_TIME = 75

TASK_TIME_LIMIT = 120  # Stop after 2 minutes

# Params for all tasks
TASK_DEFAULT_KWARGS = {"time_limit": TASK_TIME_LIMIT, "max_retries": ESI_MAX_RETRIES}


class FleetViewAggregate:  # pylint: disable=too-few-public-methods
    """
    A helper class to encapsulate fleet data and its aggregate information.

    This class is used to store and return the fleet view along with its aggregated data.
    """

    def __init__(self, fleet: list, aggregate: dict) -> None:
        """
        Initialize the FleetViewAggregate object.

        :param fleet: A list of fleet members or fleet-related data.
        :type fleet: list
        :param aggregate: A dictionary containing aggregated data about the fleet.
        :type aggregate: dict
        """

        self.fleet = fleet
        self.aggregate = aggregate


@shared_task
def _send_invitation(
    character_id: int, fleet_commander_token: Token, fleet_id: int
) -> None:
    """
    Sends a fleet invitation to a character in the EVE Online client.

    This task uses the ESI API to open the fleet invite window for a specific character,
    assigning them the role of "squad_member" in the specified fleet.

    :param character_id: The ID of the character to invite to the fleet.
    :type character_id: int
    :param fleet_commander_token: The ESI token of the fleet commander, used for authentication.
    :type fleet_commander_token: str
    :param fleet_id: The ID of the fleet to which the character is being invited.
    :type fleet_id: int
    :return: None
    :rtype: None
    """

    # Define the invitation payload with the character ID and role
    invitation = {"character_id": character_id, "role": "squad_member"}

    # Send the invitation using the ESI API
    operation = esi.client.Fleets.PostFleetsFleetIdMembers(
        fleet_id=fleet_id, token=fleet_commander_token, body=invitation
    )
    esi_handler.result(operation, use_etag=False)


def _close_esi_fleet(fleet: Fleet, reason: str) -> None:
    """
    Close a registered fleet and log the reason for closure.

    This function deletes the specified fleet from the database and logs
    the closure event with the provided reason.

    :param fleet: The fleet object to be closed.
    :type fleet: Fleet
    :param reason: The reason for closing the fleet.
    :type reason: str
    :return: None
    :rtype: None
    """

    logger.info(
        msg=(
            f'Fleet "{fleet.name}" of {fleet.fleet_commander} (ESI ID: {fleet.fleet_id}) » '
            f"Closing: {reason}"
        )
    )

    fleet.delete()


def _esi_fleet_error_handling(fleet: Fleet, error_key: str) -> None:
    """
    Handle errors related to ESI (EVE Swagger Interface) fleet operations.

    This function manages error handling for a fleet by checking the error count
    and the time of the last error. If the error count exceeds the maximum allowed
    within the grace period, the fleet is closed. Otherwise, the error count is updated
    and logged.

    :param fleet: The fleet object associated with the error.
    :type fleet: Fleet
    :param error_key: A key representing the specific error encountered.
    :type error_key: str
    :return: None
    :rtype: None
    """

    time_now = timezone.now()

    # Close ESI fleet if the consecutive error count is too high
    if (
        fleet.last_esi_error == error_key
        and fleet.last_esi_error_time
        >= (time_now - timedelta(seconds=ESI_ERROR_GRACE_TIME))
        and fleet.esi_error_count >= ESI_MAX_ERROR_COUNT
    ):
        _close_esi_fleet(fleet=fleet, reason=error_key.label)

        return

    # Increment the error count or reset it if the error is new or outside the grace period
    error_count = (
        fleet.esi_error_count + 1
        if fleet.last_esi_error == error_key
        and fleet.last_esi_error_time
        >= (time_now - timedelta(seconds=ESI_ERROR_GRACE_TIME))
        else 1
    )

    # Log the error details
    logger.info(
        f'Fleet "{fleet.name}" of {fleet.fleet_commander} (ESI ID: {fleet.fleet_id}) » '
        f'Error: "{error_key.label}" ({error_count} of {ESI_MAX_ERROR_COUNT}).'
    )

    # Update the fleet object with the new error details
    fleet.esi_error_count = error_count
    fleet.last_esi_error = error_key
    fleet.last_esi_error_time = time_now
    fleet.save()


@shared_task
def _get_fleet_aggregate(fleet_infos: list) -> dict:
    """
    Calculate the composition of a fleet based on ship types.

    This function processes a list of fleet members and counts the occurrences
    of each ship type. The result is a dictionary where the keys are ship type names
    and the values are the counts of those ship types.

    :param fleet_infos: A list of dictionaries containing fleet member information.
                        Each dictionary is expected to have a "ship_type_name" key.
    :type fleet_infos: list
    :return: A dictionary with ship type names as keys and their counts as values.
    :rtype: dict
    """

    counts = {}

    logger.debug(f"Fleet infos for aggregation: {fleet_infos}")

    for member in fleet_infos:
        logger.debug(f"Processing member for aggregation: {member}")

        # Extract the ship type name from the member information
        type_ = member.get("ship_type_name")

        # Check if the ship type name is valid and normalize it
        if type_ and isinstance(type_, str) and type_.strip():
            type_ = type_.strip()  # Normalize ship type name

            # Increment the count for the ship type or initialize it
            if type_ in counts:
                counts[type_] += 1
            else:
                counts[type_] = 1

    return counts


def _check_for_esi_fleet(fleet: Fleet) -> dict | bool:
    """
    Check if a fleet exists and retrieve its ESI (EVE Swagger Interface) data.

    This function verifies the existence of a fleet by checking the required ESI scopes
    and retrieving the fleet data using the fleet commander's token. If the fleet is not found
    or an error occurs, appropriate error handling is performed.

    :param fleet: The fleet object to check.
    :type fleet: Fleet
    :return: A dictionary containing the fleet data and the ESI token if successful, or False otherwise.
    :rtype: dict | bool
    """

    required_scopes = ["esi-fleets.read_fleet.v1"]

    fleet_commander_id = fleet.fleet_commander.character_id
    esi_token = Token.get_token(fleet_commander_id, required_scopes)

    operation = esi.client.Fleets.GetCharactersCharacterIdFleet(
        character_id=fleet_commander_id, token=esi_token
    )

    # Check if there is a fleet
    try:
        result = esi_handler.result(operation, use_etag=False)

        return {"fleet": result, "token": esi_token}
    except HTTPClientError as ex:
        logger.debug(
            f'HTTPClientError while checking fleet "{fleet.name}" of {fleet.fleet_commander} '
            f"(ESI ID: {fleet.fleet_id}): {ex}"
        )

        # Handle the case where the fleet is not found
        if ex.status_code == 404:
            _esi_fleet_error_handling(
                error_key=Fleet.EsiError.NOT_IN_FLEET, fleet=fleet
            )
        else:  # 400, 401, 402, 403 ?
            _esi_fleet_error_handling(error_key=Fleet.EsiError.NO_FLEET, fleet=fleet)
    except Exception:  # pylint: disable=broad-exception-caught
        logger.debug(
            f'Unexpected error while checking fleet "{fleet.name}" of {fleet.fleet_commander} '
            f"(ESI ID: {fleet.fleet_id})",
            exc_info=True,
        )

        # Handle any other errors that occur
        _esi_fleet_error_handling(error_key=Fleet.EsiError.NO_FLEET, fleet=fleet)

    return False


def _process_fleet(fleet: Fleet) -> None:
    """
    Process a fleet and handle its state based on ESI (EVE Swagger Interface) data.

    This function retrieves the fleet's ESI data, verifies its consistency, and performs
    appropriate error handling if discrepancies are found. It also checks if the current
    user is the fleet boss.

    :param fleet: The fleet object to process.
    :type fleet: Fleet
    :return: None
    :rtype: None
    """

    # Log the start of fleet processing
    logger.info(
        f'Processing information for fleet "{fleet.name}" '
        f"of {fleet.fleet_commander} (ESI ID: {fleet.fleet_id})"
    )

    # Check if the fleet exists in ESI
    esi_fleet = _check_for_esi_fleet(fleet=fleet)

    # Exit if the fleet does not exist
    if not esi_fleet:
        logger.debug(
            f'No ESI fleet data found for fleet "{fleet.name}" of {fleet.fleet_commander} '
            f"(ESI ID: {fleet.fleet_id}), skipping further processing."
        )

        return

    # Handle the case where fleet IDs do not match, indicating the fleet commander changed fleets
    if fleet.fleet_id != esi_fleet["fleet"].fleet_id:
        logger.debug(
            f'Fleet ID mismatch for fleet "{fleet.name}" of {fleet.fleet_commander} '
            f"(ESI ID: {fleet.fleet_id}): ESI fleet ID is {esi_fleet['fleet'].fleet_id}."
        )

        _esi_fleet_error_handling(
            fleet=fleet, error_key=Fleet.EsiError.FC_CHANGED_FLEET
        )

        return

    # Verify if the current user is the fleet boss
    operation = esi.client.Fleets.GetFleetsFleetIdMembers(
        fleet_id=fleet.fleet_id, token=esi_fleet["token"]
    )
    try:
        _ = esi_handler.result(operation, use_etag=False)
    except Exception:  # pylint: disable=broad-exception-caught
        # Handle the case where the user is not the fleet boss
        _esi_fleet_error_handling(fleet=fleet, error_key=Fleet.EsiError.NOT_FLEETBOSS)


@shared_task
def send_fleet_invitation(fleet_id: int, character_ids: list) -> None:
    """
    Send fleet invitations to characters through ESI.

    This task sends fleet invitations to a list of character IDs using the ESI API.
    It retrieves the fleet and the fleet commander's token, then processes the invitations
    concurrently using a thread pool.

    :param fleet_id: The ID of the fleet to which invitations are sent.
    :type fleet_id: int
    :param character_ids: List of character IDs to invite to the fleet.
    :type character_ids: list[int]
    :return: None
    :rtype: None
    """

    # Define the required ESI scopes for sending fleet invitations
    required_scopes = ["esi-fleets.write_fleet.v1"]

    # Retrieve the fleet object using the provided fleet ID
    fleet = Fleet.objects.get(fleet_id=fleet_id)

    # Retrieve the fleet commander's token for authentication
    fleet_commander_token = Token.get_token(
        character_id=fleet.fleet_commander.character_id, scopes=required_scopes
    )

    # Use a thread pool to send invitations concurrently
    with ThreadPoolExecutor(max_workers=50) as ex:
        # Create a list of futures for sending invitations
        futures = [
            ex.submit(
                _send_invitation,
                character_id=character_id,
                fleet_commander_token=fleet_commander_token,
                fleet_id=fleet_id,
            )
            for character_id in character_ids
        ]

        # Wait for all futures to complete and raise any exceptions that occurred
        for future in as_completed(futures):
            future.result()  # This will raise any exceptions that occurred


@shared_task(**{**TASK_DEFAULT_KWARGS}, **{"base": QueueOnce})
def check_fleet_adverts() -> None:
    """
    Check all registered fleets and process them.

    This task retrieves all registered fleets from the database and processes each fleet
    individually. It first checks if there are any fleets to process and logs the count.
    If no fleets are found, it logs a message and exits. Before processing, it ensures
    that the ESI (EVE Swagger Interface) service is available. If ESI is offline or
    above the error limit, the task aborts. Each fleet is then processed using the
    `_process_fleet` function.

    :return: None
    :rtype: None
    """

    # Retrieve all registered fleets from the database
    fleets = Fleet.objects.all()

    # Check if there are any fleets to process
    if not fleets.exists():
        logger.info("No registered fleets found. Nothing to do...")

        return

    # Log the number of fleets to be processed
    logger.info(f"Processing {fleets.count()} registered fleets...")

    # Process each fleet individually
    for fleet in fleets:
        _process_fleet(fleet=fleet)


def _fetch_chunk(ids: list) -> list:
    """
    Fetch names for a list of IDs using the ESI API.

    This function sends a request to the ESI API to retrieve names for a given list of IDs.
    If the request fails and the list contains more than one ID, the list is split into two
    halves, and the function is called recursively for each half. If the list contains only
    one ID, the ID is dropped, and a warning is logged.

    :param ids: A list of IDs to fetch names for.
    :type ids: list
    :return: A list of results containing the names corresponding to the provided IDs.
    :rtype: list
    """

    operation = esi.client.Universe.PostUniverseNames(body=ids)

    try:
        result = esi_handler.result(operation, use_etag=False)

        logger.debug(f"Fetched {len(result)} names for {len(ids)} IDs.")
        logger.debug(f"Result: {result}")

        return result
    except Exception:  # pylint: disable=broad-exception-caught
        if len(ids) == 1:
            logger.warning(f"Dropping ID {ids[0]}: failed to fetch name.")

            return []

        mid = len(ids) // 2

        return _fetch_chunk(ids[:mid]) + _fetch_chunk(ids[mid:])


def _make_name_lookup(ids_to_name: Iterable) -> dict:
    """
    Create a lookup dictionary mapping IDs to names.

    Build a mapping of id -> name from a sequence that may contain either
    dicts like {'id': ..., 'name': ...} or objects with .id and .name attributes.

    :param ids_to_name:
    :type ids_to_name:
    :return:
    :rtype:
    """

    lookup = {}

    if not ids_to_name:
        return lookup

    for item in ids_to_name:
        if item is None:
            continue

        if isinstance(item, dict):
            id_ = item.get("id")
            name = item.get("name")
        else:
            id_ = getattr(item, "id", None)
            name = getattr(item, "name", None)

        if id_ is not None and name is not None:
            lookup[id_] = name

    return lookup


@shared_task
def get_fleet_composition(fleet_id: int) -> FleetViewAggregate | None:
    """
    Retrieve the composition of a fleet by its ESI ID.

    This task fetches the fleet composition, including detailed information about its members,
    using the EVE Swagger Interface (ESI). It processes the fleet data, retrieves names for
    associated IDs, and aggregates the fleet composition based on ship types.

    :param fleet_id: The ESI ID of the fleet to retrieve.
    :type fleet_id: int
    :return: A FleetViewAggregate object containing fleet members and aggregate data, or None if an error occurs.
    :rtype: FleetViewAggregate | None
    """

    try:
        # Retrieve the fleet object from the database
        fleet = Fleet.objects.get(fleet_id=fleet_id)
    except Fleet.DoesNotExist as exc:
        # Log and raise an error if the fleet does not exist
        logger.error(f"Fleet with ID {fleet_id} not found")

        raise Fleet.DoesNotExist(f"Fleet with ID {fleet_id} not found.") from exc

    # Log the start of fleet composition retrieval
    logger.info(
        f'Getting fleet composition for fleet "{fleet.name}" '
        f"of {fleet.fleet_commander.character_name} (ESI ID: {fleet_id})"
    )

    # Retrieve the fleet commander's token for authentication
    token = Token.get_token(
        character_id=fleet.fleet_commander.character_id,
        scopes=["esi-fleets.read_fleet.v1"],
    )
    operation = esi.client.Fleets.GetFleetsFleetIdMembers(
        fleet_id=fleet_id, token=token
    )

    try:
        # Fetch fleet member information from the ESI API
        fleet_infos = esi_handler.result(operation, use_etag=False)
    except Exception as exc:  # pylint: disable=broad-exception-caught
        # Log and raise an error if fleet composition retrieval fails
        logger.error(f"Failed to get fleet composition for fleet {fleet_id}: {exc}")

        raise RuntimeError(exc) from exc

    logger.debug(f"Fleet infos: {fleet_infos}")

    # Extract all unique IDs (character, solar system, and ship type) for name resolution
    all_ids = {
        item_id
        for member in fleet_infos
        for item_id in [
            member.character_id,
            member.solar_system_id,
            member.ship_type_id,
        ]
    }

    logger.debug(
        f"Found {len(all_ids)} unique IDs to fetch names for in fleet {fleet_id}"
    )

    # Process IDs in chunks to avoid exceeding ESI limits
    chunk_size = 1000
    all_ids_list = list(all_ids)
    ids_to_name = []

    for start in range(0, len(all_ids_list), chunk_size):
        chunk = all_ids_list[start : start + chunk_size]
        results = _fetch_chunk(chunk)
        ids_to_name.extend(results)

    logger.debug(f"Fetched names for {len(ids_to_name)} IDs.")

    # Create a lookup dictionary for resolving names
    name_lookup = _make_name_lookup(ids_to_name)

    logger.debug(f"Name lookup: {name_lookup}")

    # Add detailed information to each fleet member
    member_in_fleet = [
        {
            **member.dict(),
            "takes_fleet_warp": member.takes_fleet_warp,
            "character_name": name_lookup[member.character_id],
            "solar_system_name": name_lookup[member.solar_system_id],
            "ship_type_name": name_lookup[member.ship_type_id],
            "is_fleet_boss": member.character_id == fleet.fleet_commander.character_id,
        }
        for member in fleet_infos
    ]

    logger.debug(f"Member in fleet after processing: {member_in_fleet}")

    # Return the fleet composition and aggregate data
    return FleetViewAggregate(
        fleet=member_in_fleet,
        aggregate=_get_fleet_aggregate(fleet_infos=member_in_fleet),
    )
