"""Regular views for Blueprints."""

from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.contrib.auth.models import User
from django.db import transaction
from django.db.models import QuerySet
from django.http import HttpRequest, JsonResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.utils.html import format_html
from django.utils.translation import gettext_lazy as _
from django.views.decorators.http import require_POST
from esi.decorators import token_required
from esi.models import Token
from eveuniverse.models import EveType

from allianceauth.authentication.decorators import permissions_required
from allianceauth.authentication.models import CharacterOwnership
from allianceauth.eveonline.models import EveCharacter, EveCorporationInfo
from allianceauth.services.hooks import get_extension_logger
from app_utils.allianceauth import notify_admins
from app_utils.logging import LoggerAddTag

from blueprints import __title__, tasks
from blueprints.app_settings import (
    BLUEPRINTS_ADMIN_NOTIFICATIONS_ENABLED,
    BLUEPRINTS_DEFAULT_PAGE_LENGTH,
    BLUEPRINTS_LIST_ICON_OUTPUT_SIZE,
    BLUEPRINTS_PAGING_ENABLED,
)
from blueprints.models import Blueprint, Owner, Request

logger = LoggerAddTag(get_extension_logger(__name__), __title__)


@login_required
@permissions_required("blueprints.basic_access")
def index(request: HttpRequest):
    """Render index view."""
    if request.user.has_perm("blueprints.manage_requests"):
        request_count = Request.objects.open_requests_total_count(request.user)
    else:
        request_count = None
    context = {
        "page_title": _(__title__),
        "data_tables_page_length": BLUEPRINTS_DEFAULT_PAGE_LENGTH,
        "data_tables_paging": BLUEPRINTS_PAGING_ENABLED,
        "request_count": request_count,
    }
    return render(request, "blueprints/index.html", context)


@login_required
@permissions_required("blueprints.add_corporate_blueprint_owner")
@token_required(
    scopes=[
        "esi-universe.read_structures.v1",
        "esi-corporations.read_blueprints.v1",
        "esi-assets.read_corporation_assets.v1",
        "esi-industry.read_corporation_jobs.v1",
    ]
)
def add_corporation_blueprint_owner(request: HttpRequest, token: Token):
    """Render view for adding an owner for corporation blueprints."""
    token_char = get_object_or_404(EveCharacter, character_id=token.character_id)
    success = True
    try:
        owned_char = CharacterOwnership.objects.get(
            user=request.user, character=token_char
        )
    except CharacterOwnership.DoesNotExist:
        messages.error(
            request,
            format_html(
                _(
                    "You can only use your main or alt characters "
                    "to add corporations. "
                    "However, character %s is neither. "
                )
                % format_html("<strong>{}</strong>", token_char.character_name)
            ),
        )
        success = False
        owned_char = None

    if success:
        try:
            corporation = EveCorporationInfo.objects.get(
                corporation_id=token_char.corporation_id
            )
        except EveCorporationInfo.DoesNotExist:
            corporation = EveCorporationInfo.objects.create_corporation(
                token_char.corporation_id
            )

        with transaction.atomic():
            owner = Owner.objects.update_or_create(
                corporation=corporation, defaults={"character": owned_char}
            )[0]

        tasks.update_blueprints_for_owner.delay(owner_pk=owner.pk)
        tasks.update_locations_for_owner.delay(owner_pk=owner.pk)
        messages.info(
            request,
            format_html(
                _(
                    "%(corporation)s has been added with %(character)s "
                    "as sync character. We have started fetching blueprints "
                    "for this corporation. You will receive a report once "
                    "the process is finished."
                )
                % {
                    "corporation": format_html("<strong>{}</strong>", owner),
                    "character": format_html(
                        "<strong>{}</strong>", owner.eve_character_strict.character_name
                    ),
                }
            ),
        )
        if BLUEPRINTS_ADMIN_NOTIFICATIONS_ENABLED:
            corporation_name = owner.corporation_strict.corporation_name
            notify_admins(
                message=(
                    f"{corporation_name} was added as new corporation, "
                    f"blueprint owner by {request.user.username}."
                ),
                title=f"{__title__}: blueprint owner added: {corporation_name}",
            )
    return redirect("blueprints:index")


@login_required
@permissions_required("blueprints.add_personal_blueprint_owner")
@token_required(
    scopes=[
        "esi-universe.read_structures.v1",
        "esi-characters.read_blueprints.v1",
        "esi-assets.read_assets.v1",
        "esi-industry.read_character_jobs.v1",
    ]
)
def add_personal_blueprint_owner(request: HttpRequest, token: Token):
    """Render view for adding an owner for personal blueprints."""
    token_char = get_object_or_404(EveCharacter, character_id=token.character_id)
    success = True
    try:
        owned_char = CharacterOwnership.objects.get(
            user=request.user, character=token_char
        )
    except CharacterOwnership.DoesNotExist:
        messages.error(
            request,
            format_html(
                _(
                    "You can only use your main or alt characters "
                    "to add corporations. "
                    "However, character %s is neither. "
                )
                % format_html("<strong>{}</strong>", token_char.character_name)
            ),
        )
        success = False
        owned_char = None

    if success:
        with transaction.atomic():
            owner = Owner.objects.update_or_create(
                corporation=None, character=owned_char
            )[0]

        tasks.update_blueprints_for_owner.delay(owner_pk=owner.pk)
        tasks.update_locations_for_owner.delay(owner_pk=owner.pk)
        messages.info(
            request,
            format_html(
                _(
                    "%(character)s has been added. We have started fetching blueprints "
                    "for this character. You will receive a report once "
                    "the process is finished."
                )
                % {
                    "character": format_html(
                        "<strong>{}</strong>", owner.eve_character_strict.character_name
                    ),
                }
            ),
        )
        if BLUEPRINTS_ADMIN_NOTIFICATIONS_ENABLED:
            notify_admins(
                message=(
                    f"{owner.eve_character_strict.character_name} was added "
                    "as a new personal blueprint owner."
                ),
                title=(
                    f"{__title__}: blueprint owner added: "
                    f"{owner.eve_character_strict.character_name}"
                ),
            )
    return redirect("blueprints:index")


def _convert_blueprint_for_template(
    blueprint: Blueprint, user: User, include_details: bool = False
) -> dict:
    """Convert a blueprint for use in a template."""
    variant = EveType.IconVariant.BPC if blueprint.runs else EveType.IconVariant.BPO
    icon = format_html(
        '<img src="{}" width="{}" height="{}">',
        blueprint.eve_type.icon_url(size=64, variant=variant),
        BLUEPRINTS_LIST_ICON_OUTPUT_SIZE,
        BLUEPRINTS_LIST_ICON_OUTPUT_SIZE,
    )
    runs = "" if not blueprint.runs or blueprint.runs == -1 else blueprint.runs
    original = "✓" if not blueprint.runs or blueprint.runs == -1 else ""
    filter_is_original = (
        _("Yes") if not blueprint.runs or blueprint.runs == -1 else _("No")
    )
    if blueprint.owner.corporation:
        owner_type = "corporation"
    else:
        owner_type = "character"

    if user.has_perm("blueprints.view_blueprint_locations"):
        location_name = blueprint.location.full_qualified_name()
        location_detail = blueprint.location_flag_obj.label
    else:
        location_name = location_detail = _("(no access)")
    summary = {
        "icn": icon,
        "qty": blueprint.quantity,
        "pk": blueprint.pk,
        "nme": blueprint.eve_type.name,
        "loc": location_name,
        "lfg": location_detail,
        "me": blueprint.material_efficiency,
        "te": blueprint.time_efficiency,
        "og": original,
        "iog": filter_is_original,
        "rns": runs,
        "on": blueprint.owner.name,
        "ot": owner_type,
        "use": blueprint.has_industryjob(),
    }
    if include_details:
        if blueprint.has_industryjob() and user.has_perm(
            "blueprints.view_industry_jobs"
        ):
            job = {
                "activity": blueprint.industryjob.get_activity_display(),
                "installer": blueprint.industryjob.installer.character_name,
                "runs": blueprint.industryjob.runs,
                "start_date": blueprint.industryjob.start_date,
                "end_date": blueprint.industryjob.end_date,
            }
            summary.update({"job": job})
        summary.update({"frm": blueprint.eve_type.name.endswith(" Formula")})
    return summary


# @login_required
# @permissions_required("blueprints.basic_access")
# def list_blueprints(request:  HttpRequest):
#     blueprint_rows = [
#         convert_blueprint(blueprint, request.user)
#         for blueprint in Blueprint.objects.user_has_access(request.user)
#     ]
#     return JsonResponse(blueprint_rows, safe=False)


@login_required
@permissions_required("blueprints.basic_access")
def list_blueprints_ffd(request: HttpRequest) -> JsonResponse:
    """Render view for filterDropDown endpoint to enable
    server-side processing for blueprints list.
    """
    result = {}
    blueprint_query = Blueprint.objects.user_has_access(
        request.user
    ).annotate_owner_name()
    columns = request.GET.get("columns")
    if columns:
        for column in columns.split(","):
            if column == "location":
                if request.user.has_perm("blueprints.view_blueprint_locations"):
                    options = blueprint_query.annotate_location_name().values_list(
                        "location_name", flat=True
                    )
                else:
                    options = []
            elif column == "material_efficiency":
                options = blueprint_query.values_list("material_efficiency", flat=True)
            elif column == "time_efficiency":
                options = blueprint_query.values_list("time_efficiency", flat=True)
            elif column == "owner":
                options = blueprint_query.values_list("owner_name", flat=True)
            elif column == "is_original":
                options = map(
                    lambda x: "yes" if x is None else "no",
                    blueprint_query.values_list("runs", flat=True),
                )
            else:
                options = [f"** ERROR: Invalid column name '{column}' **"]

            result[column] = sorted(list(set(options)))

    return JsonResponse(result, safe=False)


@login_required
@permissions_required(
    "blueprints.add_personal_blueprint_owner",
    "blueprints.add_corporate_blueprint_owner",
)
def list_user_owners(request: HttpRequest) -> JsonResponse:
    """Return list of owners"""
    owners: QuerySet[Owner] = Owner.objects.filter(
        character__user=request.user
    ).annotate_blueprint_count()
    results = []
    for owner in owners:
        if owner.corporation:
            owner_type = "corporate"
            owner_type_display = _("Corporate")
            owner_name = owner.corporation.corporation_name
        else:
            owner_type = "personal"
            owner_type_display = _("Personal")
            owner_name = owner.eve_character_strict.character_name
        results.append(
            {
                "id": owner.pk,
                "type": owner_type,
                "type_display": owner_type_display,
                "name": owner_name,
                "quantity": owner.blueprint_count,
            }
        )
    return JsonResponse(results, safe=False)


@login_required
def view_blueprint_modal(request: HttpRequest):
    """Render modal view for a blueprint."""
    blueprint = get_object_or_404(Blueprint, pk=request.GET.get("blueprint_id"))
    context = {
        "blueprint": _convert_blueprint_for_template(
            blueprint, request.user, include_details=True
        )
    }
    return render(request, "blueprints/modals/view_blueprint_content.html", context)


@login_required
@permissions_required(("blueprints.request_blueprints", "blueprints.manage_requests"))
def view_request_modal(request: HttpRequest):
    """Render modal view for a blueprint request."""
    user_request = get_object_or_404(Request, pk=request.GET.get("request_id"))
    context = {"request": _convert_request_for_template(user_request, request.user)}
    return render(request, "blueprints/modals/view_request_content.html", context)


@login_required
@permissions_required("blueprints.request_blueprints")
def create_request(request: HttpRequest):
    """Render view to create a blueprint request."""
    if request.method == "POST":
        requested = get_object_or_404(Blueprint, pk=request.POST.get("pk"))
        runs = request.POST.get("runs")
        if runs == "":
            runs = None
        user = request.user
        user_request = Request.objects.create(
            blueprint=requested,
            requesting_user=user,
            status=Request.STATUS_OPEN,
            runs=runs,
        )
        user_request.notify_new_request()
        messages.info(
            request,
            format_html(
                _("A copy of %(blueprint)s has been requested.")
                % {"blueprint": requested.eve_type.name}
            ),
        )
    return redirect("blueprints:index")


def _convert_request_for_template(request: Request, user: User) -> dict:
    """Convert a blueprint request for a template."""
    variant = (
        EveType.IconVariant.BPC if request.blueprint.runs else EveType.IconVariant.BPO
    )
    icon = format_html(
        '<img src="{}" width="{}" height="{}">',
        request.blueprint.eve_type.icon_url(size=64, variant=variant),
        BLUEPRINTS_LIST_ICON_OUTPUT_SIZE,
        BLUEPRINTS_LIST_ICON_OUTPUT_SIZE,
    )

    if request.blueprint.owner.corporation:
        owner_type = "corporation"
    else:
        owner_type = "character"

    if user.has_perm("blueprints.view_blueprint_locations"):
        location = request.blueprint.location.full_qualified_name()
    else:
        location = _("(Unknown)")

    return {
        "request_id": request.pk,
        "type_icon": icon,
        "type_name": request.blueprint.eve_type.name,
        "owner_name": request.blueprint.owner.name,
        "owner_type": owner_type,
        "requestor": request.requesting_character_name(),
        "location": location,
        "material_efficiency": request.blueprint.material_efficiency,
        "time_efficiency": request.blueprint.time_efficiency,
        "runs": request.runs if request.runs else "",
        "status": request.status,
        "status_display": request.get_status_display(),
    }


@login_required
@permissions_required("blueprints.request_blueprints")
def list_user_requests(request: HttpRequest):
    """Render view to list the blueprint requests of the current user."""

    request_query = Request.objects.select_related_default().filter(
        requesting_user=request.user, closed_at=None
    )
    request_rows = [
        _convert_request_for_template(req, request.user) for req in request_query
    ]

    return JsonResponse(request_rows, safe=False)


@login_required
@permissions_required("blueprints.manage_requests")
def list_open_requests(request: HttpRequest):
    """Render view to list the open blueprint requests."""

    requests = Request.objects.select_related_default().requests_fulfillable_by_user(
        request.user
    ) | Request.objects.select_related_default().requests_being_fulfilled_by_user(
        request.user
    )
    request_rows = [
        _convert_request_for_template(req, request.user) for req in requests
    ]

    return JsonResponse(request_rows, safe=False)


@login_required
@permissions_required("blueprints.manage_requests")
@require_POST
def mark_request_fulfilled(request: HttpRequest, request_id: int):
    """Render view to mark a blueprint request as fulfilled."""
    user_request = get_object_or_404(Request, pk=request_id)
    is_completed = user_request.mark_request(
        user=request.user, status=Request.STATUS_FULFILLED, closed=True
    )
    if is_completed:
        user_request.notify_request_fulfilled()
        messages.info(
            request,
            format_html(
                _("The request for %(blueprint)s has been closed as fulfilled.")
                % {"blueprint": user_request.blueprint.eve_type.name}
            ),
        )
    else:
        messages.error(
            request,
            format_html(
                _("Fulfilling the request for %(blueprint)s has failed.")
                % {"blueprint": user_request.blueprint.eve_type.name}
            ),
        )
    return redirect("blueprints:index")


@login_required
@permissions_required("blueprints.manage_requests")
@require_POST
def mark_request_in_progress(request: HttpRequest, request_id: int):
    """Render view to mark a blueprint request as in progress."""
    user_request = get_object_or_404(Request, pk=request_id)
    is_completed = user_request.mark_request(
        user=request.user, status=Request.STATUS_IN_PROGRESS, closed=False
    )
    if is_completed:
        user_request.notify_request_in_progress()
        messages.info(
            request,
            format_html(
                _("The request for %(blueprint)s has been marked as in progress.")
                % {"blueprint": user_request.blueprint.eve_type.name}
            ),
        )
    else:
        messages.error(
            request,
            format_html(
                _("Marking the request for %(blueprint)s as in progress has failed.")
                % {"blueprint": user_request.blueprint.eve_type.name}
            ),
        )
    return redirect("blueprints:index")


@login_required
@permissions_required("blueprints.manage_requests")
@require_POST
def mark_request_open(request: HttpRequest, request_id: int):
    """Render view to mark a blueprint request as open."""
    user_request = get_object_or_404(Request, pk=request_id)
    is_completed = user_request.mark_request(
        user=request.user, status=Request.STATUS_OPEN, closed=False
    )
    if is_completed:
        user_request.notify_request_reopened(request.user)
        messages.info(
            request,
            format_html(
                _("The request for %(blueprint)s has been re-opened.")
                % {"blueprint": user_request.blueprint.eve_type.name}
            ),
        )
    else:
        messages.error(
            request,
            format_html(
                _("Re-opening the request for %(blueprint)s has failed.")
                % {"blueprint": user_request.blueprint.eve_type.name}
            ),
        )
    return redirect("blueprints:index")


@login_required
@permissions_required(["blueprints.basic_access", "blueprints.manage_requests"])
@require_POST
def mark_request_cancelled(request: HttpRequest, request_id: int):
    """Render view to mark a blueprint request a canceled."""
    user_request = get_object_or_404(Request, pk=request_id)
    is_completed = user_request.mark_request(
        user=request.user,
        status=Request.STATUS_CANCELLED,
        closed=True,
        can_requestor_edit=True,
    )
    if is_completed:
        if request.user == user_request.requesting_user:
            user_request.notify_request_canceled_by_requestor()
        else:
            user_request.notify_request_canceled_by_approver(request.user)
        messages.info(
            request,
            format_html(
                _("The request for %(blueprint)s has been closed as cancelled.")
                % {"blueprint": user_request.blueprint.eve_type.name}
            ),
        )
    else:
        messages.error(
            request,
            format_html(
                _("Cancelling the request for %(blueprint)s has failed.")
                % {"blueprint": user_request.blueprint.eve_type.name}
            ),
        )
    return redirect("blueprints:index")


@login_required
@permissions_required(
    "blueprints.add_personal_blueprint_owner",
    "blueprints.add_corporate_blueprint_owner",
)
@require_POST
def remove_owner(request: HttpRequest, owner_id: int):
    """Render view for removing a given owner."""
    owner = Owner.objects.filter(pk=owner_id, character__user=request.user).first()
    completed = False
    owner_name = None

    if owner:
        owner_name = (
            owner.corporation.corporation_name
            if owner.corporation
            else owner.eve_character_strict.character_name
        )
        owner.delete()
        completed = True

    if completed:
        messages.info(
            request,
            format_html(
                _("%(owner)s has been removed as a blueprint owner.")
                % {"owner": owner_name}
            ),
        )
    else:
        messages.error(
            request,
            format_html(_("Removing the blueprint owner has failed.")),
        )
    return redirect("blueprints:index")
