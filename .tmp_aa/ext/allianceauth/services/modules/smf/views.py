import logging

from django.contrib import messages
from django.contrib.auth.decorators import login_required, permission_required
from django.shortcuts import redirect, render
from django.utils.translation import gettext_lazy as _

from allianceauth.services.forms import ServicePasswordForm

from .manager import SmfManager
from .models import SmfUser
from .tasks import SmfTasks

logger = logging.getLogger(__name__)

ACCESS_PERM = 'smf.access_smf'


@login_required
@permission_required(ACCESS_PERM)
def activate_smf(request):
    logger.debug(f"activate_smf called by user {request.user}")
    # Valid now we get the main characters
    main_character = request.user.profile.main_character

    logger.debug(
        f"Adding SMF user for user {request.user} with main character {main_character}"
    )

    result = SmfManager.add_user(
        SmfTasks.get_username(request.user),
        request.user.email,
        ['Member'],
        main_character,
    )

    # if empty we failed
    if result[0] != "":
        SmfUser.objects.update_or_create(
            user=request.user, defaults={'username': result[0]}
        )

        logger.debug(
            f"Updated authserviceinfo for user {request.user} "
            f"with SMF credentials. Updating groups."
        )

        SmfTasks.update_groups.delay(request.user.pk)

        logger.info(f"Successfully activated SMF for user {request.user}")

        messages.success(request, _('Activated SMF account.'))
        credentials = {
            'username': result[0],
            'password': result[1],
        }

        return render(
            request,
            'services/service_credentials.html',
            context={'credentials': credentials, 'service': 'SMF'},
        )

    logger.error(f"Unsuccessful attempt to activate SMF for user {request.user}")
    messages.error(request, _('An error occurred while processing your SMF account.'))

    return redirect("services:services")


@login_required
@permission_required(ACCESS_PERM)
def deactivate_smf(request):
    logger.debug(f"deactivate_smf called by user {request.user}")
    result = SmfTasks.delete_user(request.user)
    # false we failed
    if result:
        logger.info(f"Successfully deactivated SMF for user {request.user}")
        messages.success(request, _('Deactivated SMF account.'))
    else:
        logger.error(f"Unsuccessful attempt to activate SMF for user {request.user}")
        messages.error(request, _('An error occurred while processing your SMF account.'))
    return redirect("services:services")


@login_required
@permission_required(ACCESS_PERM)
def reset_smf_password(request):
    logger.debug(f"reset_smf_password called by user {request.user}")
    character = request.user.profile.main_character
    if SmfTasks.has_account(request.user) and character is not None:
        result = SmfManager.update_user_password(request.user.smf.username, character.character_id)
        # false we failed
        if result != "":
            logger.info(f"Successfully reset SMF password for user {request.user}")
            messages.success(request, _('Reset SMF password.'))
            credentials = {
                'username': request.user.smf.username,
                'password': result,
            }
            return render(request, 'services/service_credentials.html', context={'credentials': credentials, 'service': 'SMF'})
    logger.error(f"Unsuccessful attempt to reset SMF password for user {request.user}")
    messages.error(request, _('An error occurred while processing your SMF account.'))
    return redirect("services:services")


@login_required
@permission_required(ACCESS_PERM)
def set_smf_password(request):
    logger.debug(f"set_smf_password called by user {request.user}")
    if request.method == 'POST':
        logger.debug("Received POST request with form.")
        form = ServicePasswordForm(request.POST)
        logger.debug(f"Form is valid: {form.is_valid()}")
        character = request.user.profile.main_character
        if form.is_valid() and SmfTasks.has_account(request.user) and character is not None:
            password = form.cleaned_data['password']
            logger.debug(f"Form contains password of length {len(password)}")
            result = SmfManager.update_user_password(request.user.smf.username, character.character_id, password=password)
            if result != "":
                logger.info(f"Successfully set SMF password for user {request.user}")
                messages.success(request, _('Set SMF password.'))
            else:
                logger.error(f"Failed to install custom SMF password for user {request.user}")
                messages.error(request, _('An error occurred while processing your SMF account.'))
            return redirect("services:services")
    else:
        logger.debug("Request is not type POST - providing empty form.")
        form = ServicePasswordForm()

    logger.debug(f"Rendering form for user {request.user}")
    context = {'form': form, 'service': 'SMF'}
    return render(request, 'services/service_password.html', context=context)
