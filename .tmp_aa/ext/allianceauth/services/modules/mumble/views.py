import logging
from datetime import datetime, timedelta, timezone

from django.conf import settings
from django.contrib import messages
from django.contrib.auth.decorators import login_required, permission_required
from django.core.exceptions import MultipleObjectsReturned, ObjectDoesNotExist
from django.db.models import Count
from django.http import (
    Http404, HttpResponse, HttpResponseRedirect, JsonResponse,
)
from django.shortcuts import redirect, render
from django.utils.crypto import get_random_string

from esi.decorators import _check_callback
from esi.views import sso_redirect

from allianceauth.authentication.models import get_guest_state
from allianceauth.eveonline.models import EveCharacter
from allianceauth.services.abstract import (
    BaseCreatePasswordServiceAccountView, BaseDeactivateServiceAccountView,
    BaseResetPasswordServiceAccountView, BaseSetPasswordServiceAccountView,
)
from allianceauth.services.forms import ServicePasswordModelForm

from .managers import MumbleManager
from .models import MumbleUser, TempLink, TempUser

logger = logging.getLogger(__name__)


class MumblePasswordForm(ServicePasswordModelForm):
    class Meta:
        model = MumbleUser
        fields = ('password',)


class MumbleViewMixin:
    service_name = 'mumble'
    model = MumbleUser
    permission_required = 'mumble.access_mumble'


class CreateAccountMumbleView(MumbleViewMixin, BaseCreatePasswordServiceAccountView):
    pass


class DeleteMumbleView(MumbleViewMixin, BaseDeactivateServiceAccountView):
    pass


class ResetPasswordMumbleView(MumbleViewMixin, BaseResetPasswordServiceAccountView):
    pass


class SetPasswordMumbleView(MumbleViewMixin, BaseSetPasswordServiceAccountView):
    form_class = MumblePasswordForm


@login_required
@permission_required('mumble.view_connection_history')
def connection_history(request) -> HttpResponse:

    context = {
        "mumble_url": settings.MUMBLE_URL,
    }

    return render(request, 'services/mumble/mumble_connection_history.html', context)


@login_required
@permission_required("mumble.view_connection_history")
def connection_history_data(request) -> JsonResponse:
    users = MumbleUser.objects.all()
    connection_history_data = []
    for user in users:
        connection_history_data.append({
            'user': str(user),
            'display_name': user.display_name,
            'release': user.release,
            'version': user.version,
            'last_connect': user.last_connect,
            'last_disconnect': user.last_disconnect,
        })

    return JsonResponse({"connection_history_data": list(connection_history_data)})


@login_required
@permission_required("mumble.view_connection_history")
def release_counts_data(request) -> JsonResponse:
    release_counts_data = MumbleUser.objects.values('release').annotate(user_count=Count('user_id')).order_by('release')

    return JsonResponse({
        "release_counts_data": list(release_counts_data),
    })


@login_required
@permission_required("mumble.view_connection_history")
def release_pie_chart_data(request) -> JsonResponse:
    release_counts = MumbleUser.objects.values('release').annotate(user_count=Count('user_id')).order_by('release')

    return JsonResponse({
        "labels": list(release_counts.values_list("release", flat=True)),
        "values": list(release_counts.values_list("user_count", flat=True)),
    })


@login_required
@permission_required("mumble.create_new_links")
def templinks(request) -> HttpResponse:
    tl = None

    if request.method == "POST":
        duration = request.POST.get("time")

        if duration in ["3", "6", "12", "24"]:
            tl = TempLink.objects.create(
                creator=request.user.profile.main_character,
                link_ref=get_random_string(15),
                expires=datetime.now(timezone.utc) + timedelta(hours=int(duration))
            )
            tl.save()

    tl_list = TempLink.objects.prefetch_related("creator").filter(expires__gte=datetime.now(timezone.utc))
    ex_tl_list = TempLink.objects.prefetch_related("creator").filter(expires__lt=datetime.now(timezone.utc))

    context = {
        "tl": tl,
        "text": "Make Links",
        "tl_list": tl_list,
        "ex_tl_list": ex_tl_list,
    }

    return render(
        request=request, template_name="services/mumble/templinks/templinks.html", context=context
    )


def link(request, link_ref) -> HttpResponse | HttpResponseRedirect:
    try:
        templink = TempLink.objects.get(link_ref=link_ref, expires__gte=datetime.now(timezone.utc))
    except ObjectDoesNotExist:
        raise Http404("Temp Link Does not Exist")

    token = _check_callback(request=request)
    if token:
        return link_sso(request=request, token=token, link=templink)

    if request.method == "POST":
        if request.POST.get("sso", False) == "True":
            # The user has chosen to SSO Login
            return sso_redirect(request=request, scopes=["publicData"])

    context = {"link": templink}

    return render(
        request=request, template_name="services/mumble/templinks/login.html", context=context
    )


def link_sso(request, token, link) -> HttpResponse:
    try:
        char = EveCharacter.objects.get(character_id=token.character_id)
    except ObjectDoesNotExist:
        try:  # create a new character, we should not get here.
            char = EveCharacter.objects.update_character(
                character_id=token.character_id
            )
        except:  # noqa: E722
            pass  # Yeah… ain't gonna happen
    except MultipleObjectsReturned:
        pass  # authenticator won't care…, but the DB will be unhappy.

    username = get_random_string(length=10)

    while TempUser.objects.filter(username=username).exists():  # force unique
        username = get_random_string(length=10)

    password = get_random_string(length=15)

    temp_user = TempUser.objects.create(
        username=username,
        pwhash=MumbleManager.gen_pwhash(password),
        templink=link,
        character=char,
    )

    context = {
        "temp_user": temp_user,
        "password": password,
        "connect_url": f"{username}:{password}@{settings.MUMBLE_URL}",
        "mumble_url": settings.MUMBLE_URL,
    }

    return render(
        request=request, template_name="services/mumble/templinks/link_sso.html", context=context
    )


@login_required
@permission_required("mumble.create_new_links")
def nuke(request, link_ref) -> HttpResponseRedirect:
    try:
        TempLink.objects.get(link_ref=link_ref).delete()
        TempUser.objects.filter(templink__isnull=True).delete()

        messages.success(request=request, message=f"Deleted Templink {link_ref}")
    except:  # noqa: E722
        messages.error(request=request, message=f"Failed to delete Templink {link_ref}")
        pass  # Crappy link

    return redirect(to="mumble:templinks")
