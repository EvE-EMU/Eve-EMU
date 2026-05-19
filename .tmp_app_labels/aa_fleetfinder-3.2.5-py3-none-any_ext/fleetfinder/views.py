"""
Views
"""

# Standard Library
import json
from http import HTTPStatus

# Django
from django.contrib import messages
from django.contrib.auth.decorators import login_required, permission_required
from django.core.handlers.wsgi import WSGIRequest
from django.db.models import Q
from django.http import JsonResponse
from django.shortcuts import redirect, render
from django.urls import reverse
from django.utils import timezone
from django.utils.functional import Promise
from django.utils.safestring import mark_safe
from django.utils.translation import gettext_lazy as _

# Alliance Auth
from allianceauth.eveonline.evelinks.eveimageserver import character_portrait_url
from allianceauth.eveonline.models import EveCharacter
from allianceauth.framework.api.user import get_all_characters_from_user
from allianceauth.groupmanagement.models import AuthGroup
from allianceauth.services.hooks import get_extension_logger
from esi.decorators import token_required
from esi.exceptions import HTTPClientError
from esi.models import Token
from esi.openapi_clients import EsiOperation

# AA Fleet Finder
from fleetfinder import __title__
from fleetfinder.handler import esi_handler
from fleetfinder.models import Fleet
from fleetfinder.providers import AppLogger, esi
from fleetfinder.tasks import get_fleet_composition, send_fleet_invitation

logger = AppLogger(my_logger=get_extension_logger(name=__name__), prefix=__title__)


@login_required()
@permission_required(perm="fleetfinder.access_fleetfinder")
def _get_and_validate_fleet(token: Token, character_id: int) -> EsiOperation:
    """
    Get fleet information and validate fleet commander permissions

    :param token: Token object containing the access token
    :type token: Token
    :param character_id: The character ID of the fleet commander
    :type character_id: int
    :return: Fleet information from ESI
    :rtype: GetCharactersCharacterIdFleetOperation
    """

    try:
        operation = esi.client.Fleets.GetCharactersCharacterIdFleet(
            character_id=token.character_id,
            token=token,
        )
        fleet_result = esi_handler.result(operation, use_etag=False)
    except HTTPClientError as ex:
        logger.debug(f"ESI fleet cannot be retrieved: {str(ex)}", exc_info=True)

        raise ValueError("Fleet not found") from ex
    except Exception as ex:
        logger.debug(f"Error retrieving fleet from ESI: {str(ex)}", exc_info=True)

        raise RuntimeError(f"Error retrieving fleet from ESI: {str(ex)}") from ex

    logger.debug(f"Fleet result: {fleet_result}")

    fleet_id = fleet_result.fleet_id
    fleet_boss_id = fleet_result.fleet_boss_id

    if not fleet_id:
        fleet_commander = EveCharacter.objects.get(character_id=token.character_id)

        raise ValueError(f"No fleet found for {fleet_commander.character_name}")

    if fleet_boss_id != character_id:
        fleet_commander = EveCharacter.objects.get(character_id=token.character_id)

        raise ValueError(f"{fleet_commander.character_name} is not the fleet boss")

    return fleet_result


@login_required()
@permission_required(perm="fleetfinder.access_fleetfinder")
def dashboard(request):
    """
    Dashboard view

    :param request:
    :return:
    """

    context = {}

    logger.info(msg=f"Module called by {request.user}")

    return render(
        request=request,
        template_name="fleetfinder/dashboard.html",
        context=context,
    )


@login_required()
@permission_required(perm="fleetfinder.access_fleetfinder")
def ajax_dashboard(request) -> JsonResponse:  # pylint: disable=too-many-locals
    """
    Ajax :: Dashboard information

    :param request:
    :return:
    """

    def _create_button_style_link(
        url: str, fa_icon_class: str, btn_title: str | Promise, btn_modifier_class: str
    ) -> str:
        """
        Helper function to create a button HTML string
        This function generates an HTML anchor tag styled as a button with an icon.

        :param url: The URL the button should link to
        :type url: str
        :param fa_icon_class: The Font Awesome class for the icon to be displayed
        :type fa_icon_class: str
        :param btn_title: The title attribute for the button, typically a translation string
        :type btn_title: str | Promise
        :param btn_modifier_class: The Bootstrap modifier class for the button styling
        :type btn_modifier_class: str
        :return: An HTML string representing the button
        :rtype: str
        """

        return (
            f'<a href="{url}" class="btn btn-sm {btn_modifier_class} ms-1" '
            f'data-bs-tooltip="aa-fleetfinder" title="{btn_title}">'
            f'<i class="{fa_icon_class}"></i></a>'
        )

    def _get_fleet_commander_information(fleet: Fleet) -> tuple[str, str]:
        """
        Helper function to get the fleet commander's HTML representation
        This function retrieves the fleet commander's name and portrait URL,
        and returns an HTML string with the portrait image and name.

        :param fleet: The Fleet object containing the fleet commander's information
        :type fleet: Fleet
        :return: A tuple containing the HTML string for the fleet commander and the name for sorting
        :rtype: tuple[str, str]
        """

        commander_name = fleet.fleet_commander.character_name
        portrait_url = character_portrait_url(
            character_id=fleet.fleet_commander.character_id, size=32
        )
        portrait_img = (
            '<img class="rounded eve-character-portrait" '
            f'src="{portrait_url}" alt="{commander_name}" loading="lazy">'
        )

        return portrait_img + commander_name, commander_name

    data = []
    groups = request.user.groups.all()
    user_characters = get_all_characters_from_user(user=request.user)
    fleets = (
        Fleet.objects.filter(
            Q(groups__group__in=groups)
            | Q(groups__isnull=True)
            | Q(fleet_commander__in=user_characters)
        )
        .distinct()
        .order_by("name")
    )

    can_manage_fleets = request.user.has_perm("fleetfinder.manage_fleets")

    for fleet in fleets:
        fleet_commander_html, fleet_commander_name = _get_fleet_commander_information(
            fleet
        )

        # Create buttons
        buttons = [
            _create_button_style_link(
                reverse("fleetfinder:join_fleet", args=[fleet.fleet_id]),
                "fa-solid fa-right-to-bracket",
                _("Join fleet"),
                "btn-success",
            )
        ]

        if can_manage_fleets:
            buttons.extend(
                [
                    _create_button_style_link(
                        reverse("fleetfinder:fleet_details", args=[fleet.fleet_id]),
                        "fa-solid fa-eye",
                        _("View fleet details"),
                        "btn-info",
                    ),
                    _create_button_style_link(
                        reverse("fleetfinder:edit_fleet", args=[fleet.fleet_id]),
                        "fa-solid fa-pen-to-square",
                        _("Edit fleet advert"),
                        "btn-warning",
                    ),
                ]
            )

        data.append(
            {
                "fleet_commander": {
                    "html": fleet_commander_html,
                    "sort": fleet_commander_name,
                },
                "fleet_name": fleet.name,
                "created_at": fleet.created_at,
                "actions": "".join(buttons),
            }
        )

    return JsonResponse(data=data, safe=False)


@login_required()
@permission_required(perm="fleetfinder.manage_fleets")
@token_required(scopes=("esi-fleets.read_fleet.v1", "esi-fleets.write_fleet.v1"))
def create_fleet(request, token):
    """
    Create fleet view

    :param request:
    :param token:
    :return:
    """

    # Validate the token and check if the character is in a fleet and is the fleet boss
    try:
        _get_and_validate_fleet(token, token.character_id)
    except (HTTPClientError, ValueError) as ex:
        error_detail = str(ex)

        logger.debug(f"Error during fleet creation: {error_detail}", exc_info=True)

        messages.error(
            request,
            mark_safe(
                _(
                    "<h4>Error!</h4><p>There was an error creating the fleet: {error_detail}</p>"
                ).format(error_detail=error_detail)
            ),
        )

        return redirect("fleetfinder:dashboard")

    if request.method != "POST":
        return redirect("fleetfinder:dashboard")

    auth_groups = AuthGroup.objects.filter(internal=False)
    context = {"character_id": token.character_id, "auth_groups": auth_groups}

    return render(
        request=request,
        template_name="fleetfinder/create-fleet.html",
        context=context,
    )


@login_required()
@permission_required(perm="fleetfinder.manage_fleets")
def edit_fleet(request, fleet_id):
    """
    Fleet edit view

    :param request:
    :param fleet_id:
    :return:
    """

    try:
        fleet = Fleet.objects.get(fleet_id=fleet_id)
    except Fleet.DoesNotExist:
        logger.debug(f"Fleet with ID {fleet_id} does not exist.")

        messages.error(
            request,
            mark_safe(
                _(
                    "<h4>Error!</h4><p>Fleet does not exist or is no longer available.</p>"
                )
            ),
        )

        return redirect("fleetfinder:dashboard")

    auth_groups = AuthGroup.objects.filter(internal=False)

    context = {
        "character_id": fleet.fleet_commander.character_id,
        "auth_groups": auth_groups,
        "fleet": fleet,
    }

    logger.debug(f"Context for fleet edit: {context}")
    logger.info(msg=f"Fleet {fleet_id} edit view by {request.user}")

    return render(
        request=request,
        template_name="fleetfinder/edit-fleet.html",
        context=context,
    )


@login_required()
@permission_required(perm="fleetfinder.access_fleetfinder")
def join_fleet(request, fleet_id):
    """
    Join fleet view

    :param request:
    :param fleet_id:
    :return:
    """

    context = {}
    groups = request.user.groups.all()
    fleet = Fleet.objects.filter(
        Q(groups__group__in=groups) | Q(groups=None), fleet_id=fleet_id
    ).count()

    if fleet == 0:
        return redirect(to="fleetfinder:dashboard")

    if request.method == "POST":
        character_ids = request.POST.getlist(key="character_ids", default=[])
        send_fleet_invitation.delay(character_ids=character_ids, fleet_id=fleet_id)

        return redirect(to="fleetfinder:dashboard")

    characters = (
        EveCharacter.objects.filter(character_ownership__user=request.user)
        .select_related()
        .order_by("character_name")
    )

    context["characters"] = characters

    return render(
        request=request,
        template_name="fleetfinder/join-fleet.html",
        context=context,
    )


@login_required()
@permission_required("fleetfinder.manage_fleets")
def save_fleet(request):
    """
    Save fleet

    :param request:
    :return:
    """

    def _edit_or_create_fleet(
        character_id: int,
        free_move: bool,
        name: str,
        groups: list,
        motd: str = None,  # pylint: disable=unused-argument
    ) -> None:
        """
        Edit or create a fleet from a fleet in EVE Online

        :param character_id: The character ID of the fleet commander
        :type character_id: int
        :param free_move: Whether the fleet is free move or not
        :type free_move: bool
        :param name: Name of the fleet
        :type name: str
        :param groups: Groups that are allowed to access the fleet
        :type groups: list[AuthGroup]
        :param motd: Message of the Day for the fleet
        :type motd: str
        :return: None
        :rtype: None
        """

        required_scopes = ["esi-fleets.read_fleet.v1", "esi-fleets.write_fleet.v1"]
        token = Token.get_token(character_id=character_id, scopes=required_scopes)

        fleet_result = _get_and_validate_fleet(token, character_id)
        fleet_commander = EveCharacter.objects.get(character_id=character_id)
        fleet_id = fleet_result.fleet_id

        fleet, created = Fleet.objects.get_or_create(
            fleet_id=fleet_id,
            defaults={
                "created_at": timezone.now(),
                # "motd": motd,
                "is_free_move": free_move,
                "fleet_commander": fleet_commander,
                "name": name,
            },
        )

        if not created:
            fleet.is_free_move = free_move
            fleet.name = name
            fleet.save()

        fleet.groups.set(groups)

        operation = esi.client.Fleets.PutFleetsFleetId(
            fleet_id=fleet_id,
            token=token,
            # body={"is_free_move": free_move, "motd": motd},
            body={"is_free_move": free_move},
        )
        esi_handler.result(operation, use_etag=False)

    if request.method != "POST":
        return redirect("fleetfinder:dashboard")

    # Extract form data
    form_data = {
        "character_id": int(request.POST["character_id"]),
        "free_move": request.POST.get("free_move") == "on",
        # "motd": request.POST.get("motd", ""),
        "name": request.POST.get("name", ""),
        "groups": request.POST.getlist("groups", []),
    }

    logger.debug(f"Form data for fleet creation: {form_data}")

    try:
        _edit_or_create_fleet(**form_data)
    except HTTPClientError as ex:
        esi_error = str(ex)

        logger.debug(f"ESI returned 404 for fleet creation: {esi_error}", exc_info=True)

        messages.error(
            request,
            mark_safe(
                _(
                    "<h4>Error!</h4><p>ESI returned the following error: {esi_error}</p>"
                ).format(esi_error=esi_error)
            ),
        )
    except ValueError as ex:
        logger.debug(f"Value error during fleet creation: {ex}", exc_info=True)

        messages.error(
            request,
            mark_safe(
                _(
                    "<h4>Error!</h4><p>There was an error creating the fleet: {ex}</p>"
                ).format(ex=str(ex))
            ),
        )

    return redirect("fleetfinder:dashboard")


@login_required()
@permission_required(perm="fleetfinder.manage_fleets")
def fleet_details(request, fleet_id):
    """
    Fleet details view

    :param request:
    :param fleet_id:
    :return:
    """

    try:
        fleet = Fleet.objects.get(fleet_id=fleet_id)
    except Fleet.DoesNotExist:
        logger.debug(f"Fleet with ID {fleet_id} does not exist.")

        messages.error(
            request,
            mark_safe(
                _(
                    "<h4>Error!</h4><p>Fleet does not exist or is no longer available.</p>"
                )
            ),
        )

        return redirect("fleetfinder:dashboard")

    context = {"fleet": fleet}

    logger.info(msg=f"Fleet {fleet.fleet_id} details view called by {request.user}")

    return render(
        request=request,
        template_name="fleetfinder/fleet-details.html",
        context=context,
    )


@login_required()
@permission_required(perm="fleetfinder.manage_fleets")
def ajax_fleet_details(
    request, fleet_id  # pylint: disable=unused-argument
) -> JsonResponse:
    """
    Ajax :: Fleet Details

    :param request:
    :param fleet_id:
    """

    try:
        fleet = get_fleet_composition(fleet_id)
    except Fleet.DoesNotExist:
        logger.debug(f"Fleet with ID {fleet_id} does not exist.")

        return JsonResponse(
            data={
                "error": _("Fleet with ID {fleet_id} does not exist.").format(
                    fleet_id=fleet_id
                )
            },
            safe=False,
        )
    except RuntimeError as ex:
        logger.debug(f"Error retrieving fleet composition: {str(ex)}", exc_info=True)

        return JsonResponse(
            data={
                "error": _("Error retrieving fleet composition: {ex}").format(
                    ex=str(ex)
                )
            },
            safe=False,
        )

    data = {
        "fleet_member": list(fleet.fleet),
        "fleet_composition": [
            {"ship_type_name": ship, "number": number}
            for ship, number in fleet.aggregate.items()
        ],
    }

    return JsonResponse(data=data, safe=False)


@login_required()
@permission_required(perm="fleetfinder.manage_fleets")
def ajax_fleet_kick_member(  # pylint: disable=too-many-return-statements
    request: WSGIRequest, fleet_id: int
) -> JsonResponse:
    """
    Ajax :: Kick member from fleet

    :param request: WSGIRequest object containing the request data
    :type request: WSGIRequest
    :param fleet_id: The ID of the fleet from which to kick a member
    :type fleet_id: int
    :return: JsonResponse indicating success or failure of the operation
    :rtype: JsonResponse
    """

    if request.method != "POST":
        return JsonResponse(
            data={"success": False, "error": _("Method not allowed")},
            status=HTTPStatus.METHOD_NOT_ALLOWED,
        )

    try:
        fleet = Fleet.objects.get(fleet_id=fleet_id)
        data = json.loads(request.body)
        member_id = data.get("memberId")

        if not member_id:
            return JsonResponse(
                data={"success": False, "error": _("Member ID required")},
                status=HTTPStatus.BAD_REQUEST,
            )

        logger.debug(f"Request data for kicking member: {data}")

        token = Token.get_token(
            character_id=fleet.fleet_commander.character_id,
            scopes=["esi-fleets.write_fleet.v1"],
        )

        operation = esi.client.Fleets.DeleteFleetsFleetIdMembersMemberId(
            fleet_id=fleet_id,
            member_id=member_id,
            token=token,
        )
        esi_handler.result(operation, use_etag=False)

        return JsonResponse(data={"success": True}, status=HTTPStatus.OK)
    except Fleet.DoesNotExist:
        return JsonResponse(
            data={"success": False, "error": _("Fleet not found")},
            status=HTTPStatus.NOT_FOUND,
        )
    except (json.JSONDecodeError, ValueError):
        return JsonResponse(
            data={"success": False, "error": _("Invalid request data")},
            status=HTTPStatus.BAD_REQUEST,
        )
    except HTTPClientError as ex:
        if ex.status_code == HTTPStatus.NOT_FOUND:
            return JsonResponse(
                data={"success": False, "error": _("Member not found in fleet")},
                status=HTTPStatus.NOT_FOUND,
            )

        logger.debug(f"ESI error while kicking member: {str(ex)}", exc_info=True)

        return JsonResponse(
            data={
                "success": False,
                "error": _("An ESI error occurred: {ex}").format(ex=str(ex)),
            },
            status=ex.status_code,
        )
