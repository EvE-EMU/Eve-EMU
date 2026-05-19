import logging

from django.contrib import messages
from django.contrib.auth.decorators import login_required, permission_required
from django.shortcuts import redirect, render
from django.utils.translation import gettext_lazy as _

from allianceauth.services.forms import ServicePasswordForm

from .manager import Phpbb3Manager
from .models import Phpbb3User
from .tasks import Phpbb3Tasks

logger = logging.getLogger(__name__)

ACCESS_PERM = 'phpbb3.access_phpbb3'


@login_required
@permission_required(ACCESS_PERM)
def activate_forum(request):
    logger.debug(f"activate_forum called by user {request.user}")
    # Valid now we get the main characters
    character = request.user.profile.main_character
    logger.debug(f"Adding phpbb user for user {request.user} with main character {character}")
    result = Phpbb3Manager.add_user(Phpbb3Tasks.get_username(request.user), request.user.email, ['REGISTERED'],
                                    character.character_id)
    # if empty we failed
    if result[0] != "":
        Phpbb3User.objects.update_or_create(user=request.user, defaults={'username': result[0]})
        logger.debug(f"Updated authserviceinfo for user {request.user} with forum credentials. Updating groups.")
        Phpbb3Tasks.update_groups.delay(request.user.pk)
        logger.info(f"Successfully activated forum for user {request.user}")
        messages.success(request, _('Activated forum account.'))
        credentials = {
            'username': result[0],
            'password': result[1],
        }
        return render(request, 'services/service_credentials.html', context={'credentials': credentials, 'service': 'Forum'})
    else:
        logger.error(f"Unsuccessful attempt to activate forum for user {request.user}")
        messages.error(request, _('An error occurred while processing your forum account.'))
    return redirect("services:services")


@login_required
@permission_required(ACCESS_PERM)
def deactivate_forum(request):
    logger.debug(f"deactivate_forum called by user {request.user}")
    # false we failed
    if Phpbb3Tasks.delete_user(request.user):
        logger.info(f"Successfully deactivated forum for user {request.user}")
        messages.success(request, _('Deactivated forum account.'))
    else:
        logger.error(f"Unsuccessful attempt to activate forum for user {request.user}")
        messages.error(request, _('An error occurred while processing your forum account.'))
    return redirect("services:services")


@login_required
@permission_required(ACCESS_PERM)
def reset_forum_password(request):
    logger.debug(f"reset_forum_password called by user {request.user}")
    if Phpbb3Tasks.has_account(request.user):
        character = request.user.profile.main_character
        result = Phpbb3Manager.update_user_password(request.user.phpbb3.username, character.character_id)
        # false we failed
        if result != "":
            logger.info(f"Successfully reset forum password for user {request.user}")
            messages.success(request, _('Reset forum password.'))
            credentials = {
                'username': request.user.phpbb3.username,
                'password': result,
            }
            return render(request, 'services/service_credentials.html', context={'credentials': credentials, 'service': 'Forum'})

    logger.error(f"Unsuccessful attempt to reset forum password for user {request.user}")
    messages.error(request, _('An error occurred while processing your forum account.'))
    return redirect("services:services")


@login_required
@permission_required(ACCESS_PERM)
def set_forum_password(request):
    logger.debug(f"set_forum_password called by user {request.user}")
    if request.method == 'POST':
        logger.debug("Received POST request with form.")
        form = ServicePasswordForm(request.POST)
        logger.debug(f"Form is valid: {form.is_valid()}")
        if form.is_valid() and Phpbb3Tasks.has_account(request.user):
            password = form.cleaned_data['password']
            logger.debug(f"Form contains password of length {len(password)}")
            character = request.user.profile.main_character
            result = Phpbb3Manager.update_user_password(request.user.phpbb3.username, character.character_id,
                                                        password=password)
            if result != "":
                logger.info(f"Successfully set forum password for user {request.user}")
                messages.success(request, _('Set forum password.'))
            else:
                logger.error(f"Failed to install custom forum password for user {request.user}")
                messages.error(request, _('An error occurred while processing your forum account.'))
            return redirect("services:services")
    else:
        logger.debug("Request is not type POST - providing empty form.")
        form = ServicePasswordForm()

    logger.debug(f"Rendering form for user {request.user}")
    context = {'form': form, 'service': 'Forum'}
    return render(request, 'services/service_password.html', context=context)
