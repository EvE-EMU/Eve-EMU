import logging

from django.conf import settings
from django.contrib import messages
from django.contrib.admin.views.decorators import staff_member_required
from django.contrib.auth.decorators import login_required, permission_required
from django.shortcuts import redirect, render
from django.utils.translation import gettext_lazy as _

from .forms import TeamspeakJoinForm
from .manager import Teamspeak3Manager
from .models import Teamspeak3User
from .tasks import Teamspeak3Tasks

logger = logging.getLogger(__name__)

ACCESS_PERM = 'teamspeak3.access_teamspeak3'


@login_required
@permission_required(ACCESS_PERM)
def activate_teamspeak3(request):
    logger.debug(f"activate_teamspeak3 called by user {request.user}")

    character = request.user.profile.main_character
    with Teamspeak3Manager() as ts3man:
        logger.debug(f"Adding TeamSpeak3 user for user {request.user} with main character {character}")
        result = ts3man.add_user(request.user, Teamspeak3Tasks.get_username(request.user))

    # if its empty we failed
    if result[0] != "":
        Teamspeak3User.objects.update_or_create(user=request.user, defaults={'uid': result[0], 'perm_key': result[1]})
        logger.debug(f"Updated authserviceinfo for user {request.user} with TeamSpeak3 credentials. Updating groups.")
        logger.info(f"Successfully activated TeamSpeak3 for user {request.user}")
        messages.success(request, _('Activated TeamSpeak3 account.'))
        return redirect("teamspeak3:verify")
    logger.error(f"Unsuccessful attempt to activate TeamSpeak3 for user {request.user}")
    messages.error(request, _('An error occurred while processing your TeamSpeak3 account.'))
    return redirect("services:services")


@login_required
@permission_required(ACCESS_PERM)
def verify_teamspeak3(request):
    logger.debug(f"verify_teamspeak3 called by user {request.user}")
    if not Teamspeak3Tasks.has_account(request.user):
        logger.warning(f"Unable to validate user {request.user} teamspeak: no teamspeak data")
        return redirect("services:services")
    if request.method == "POST":
        form = TeamspeakJoinForm(request.POST)
        if form.is_valid():
            Teamspeak3Tasks.update_groups.delay(request.user.pk)
            logger.debug(f"Validated user {request.user} joined TS server")
            return redirect("services:services")
    else:
        form = TeamspeakJoinForm(initial={'username': request.user.teamspeak3.uid})
    context = {
        'form': form,
        'authinfo': {'teamspeak3_uid': request.user.teamspeak3.uid, 'teamspeak3_perm_key': request.user.teamspeak3.perm_key},
        'public_url': settings.TEAMSPEAK3_PUBLIC_URL,
    }
    return render(request, 'services/teamspeak3/teamspeakjoin.html', context=context)


@login_required
@permission_required(ACCESS_PERM)
def deactivate_teamspeak3(request):
    logger.debug(f"deactivate_teamspeak3 called by user {request.user}")
    if Teamspeak3Tasks.has_account(request.user) and Teamspeak3Tasks.delete_user(request.user):
        logger.info(f"Successfully deactivated TeamSpeak3 for user {request.user}")
        messages.success(request, _('Deactivated TeamSpeak3 account.'))
    else:
        logger.error(f"Unsuccessful attempt to deactivate TeamSpeak3 for user {request.user}")
        messages.error(request, _('An error occurred while processing your TeamSpeak3 account.'))
    return redirect("services:services")


@login_required
@permission_required(ACCESS_PERM)
def reset_teamspeak3_perm(request):
    logger.debug(f"reset_teamspeak3_perm called by user {request.user}")
    if not Teamspeak3Tasks.has_account(request.user):
        return redirect("services:services")
    logger.debug(f"Deleting TeamSpeak3 user for user {request.user}")
    with Teamspeak3Manager() as ts3man:
        ts3man.delete_user(request.user.teamspeak3.uid)

        logger.debug(f"Generating new permission key for user {request.user}")
        result = ts3man.generate_new_permissionkey(request.user.teamspeak3.uid, request.user, Teamspeak3Tasks.get_username(request.user))

    # if blank we failed
    if result[0] != "":
        Teamspeak3User.objects.update_or_create(user=request.user, defaults={'uid': result[0], 'perm_key': result[1]})
        logger.debug(f"Updated authserviceinfo for user {request.user} with TeamSpeak3 credentials. Updating groups.")
        Teamspeak3Tasks.update_groups.delay(request.user.pk)
        logger.info(f"Successfully reset TeamSpeak3 permission key for user {request.user}")
        messages.success(request, _('Reset TeamSpeak3 permission key.'))
    else:
        logger.error(f"Unsuccessful attempt to reset TeamSpeak3 permission key for user {request.user}")
        messages.error(request, _('An error occurred while processing your TeamSpeak3 account.'))
    return redirect("services:services")


@login_required
@staff_member_required
def admin_update_ts3_groups(request):
    Teamspeak3Tasks.run_ts3_group_update.delay()
    messages.info(request, "Started updating TeamSpeak3 server groups...")
    return redirect("admin:teamspeak3_authts_changelist")
