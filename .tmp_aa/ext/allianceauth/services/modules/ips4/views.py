import logging

from django.contrib import messages
from django.contrib.auth.decorators import login_required, permission_required
from django.shortcuts import redirect, render
from django.utils.translation import gettext_lazy as _

from allianceauth.services.forms import ServicePasswordForm

from .manager import Ips4Manager
from .models import Ips4User
from .tasks import Ips4Tasks

logger = logging.getLogger(__name__)

ACCESS_PERM = 'ips4.access_ips4'


@login_required
@permission_required(ACCESS_PERM)
def activate_ips4(request):
    logger.debug(f"activate_ips4 called by user {request.user}")
    character = request.user.profile.main_character
    logger.debug(f"Adding IPS4 user for user {request.user} with main character {character}")
    result = Ips4Manager.add_user(Ips4Tasks.get_username(request.user), request.user.email)
    # if empty we failed
    if result[0] != "" and not Ips4Tasks.has_account(request.user):
        Ips4User.objects.create(user=request.user, id=result[2], username=result[0])
        logger.debug(f"Updated authserviceinfo for user {request.user} with IPSuite4 credentials.")
        # update_ips4_groups.delay(request.user.pk)
        logger.info(f"Successfully activated IPSuite4 for user {request.user}")
        messages.success(request, _('Activated IPSuite4 account.'))
        credentials = {
            'username': result[0],
            'password': result[1],
        }
        return render(request, 'services/service_credentials.html', context={'credentials': credentials, 'service': 'IPSuite4'})
    else:
        logger.error(f"Unsuccessful attempt to activate IPSuite4 for user {request.user}")
        messages.error(request, _('An error occurred while processing your IPSuite4 account.'))
    return redirect("services:services")


@login_required
@permission_required(ACCESS_PERM)
def reset_ips4_password(request):
    logger.debug(f"reset_ips4_password called by user {request.user}")
    if Ips4Tasks.has_account(request.user):
        result = Ips4Manager.update_user_password(request.user.ips4.username)
        # false we failed
        if result != "":
            logger.info(f"Successfully reset IPSuite4 password for user {request.user}")
            messages.success(request, _('Reset IPSuite4 password.'))
            credentials = {
                'username': request.user.ips4.username,
                'password': result,
            }
            return render(request, 'services/service_credentials.html', context={'credentials': credentials, 'service': 'IPSuite4'})

    logger.error(f"Unsuccessful attempt to reset IPSuite4 password for user {request.user}")
    messages.error(request, _('An error occurred while processing your IPSuite4 account.'))
    return redirect("services:services")


@login_required
@permission_required(ACCESS_PERM)
def set_ips4_password(request):
    logger.debug(f"set_ips4_password called by user {request.user}")
    if request.method == 'POST':
        logger.debug("Received POST request with form.")
        form = ServicePasswordForm(request.POST)
        logger.debug(f"Form is valid: {form.is_valid()}")
        if form.is_valid() and Ips4Tasks.has_account(request.user):
            password = form.cleaned_data['password']
            logger.debug(f"Form contains password of length {len(password)}")
            result = Ips4Manager.update_custom_password(request.user.ips4.username, plain_password=password)
            if result != "":
                logger.info(f"Successfully set IPSuite4 password for user {request.user}")
                messages.success(request, _('Set IPSuite4 password.'))
            else:
                logger.error(f"Failed to install custom IPSuite4 password for user {request.user}")
                messages.error(request, _('An error occurred while processing your IPSuite4 account.'))
            return redirect('services:services')
    else:
        logger.debug("Request is not type POST - providing empty form.")
        form = ServicePasswordForm()

    logger.debug(f"Rendering form for user {request.user}")
    context = {'form': form, 'service': 'IPS4'}
    return render(request, 'services/service_password.html', context=context)


@login_required
@permission_required(ACCESS_PERM)
def deactivate_ips4(request):
    logger.debug(f"deactivate_ips4 called by user {request.user}")
    if Ips4Tasks.delete_user(request.user):
        logger.info(f"Successfully deactivated IPSuite4 for user {request.user}")
        messages.success(request, _('Deactivated IPSuite4 account.'))
    else:
        logger.error(f"Unsuccessful attempt to deactivate IPSuite4 for user {request.user}")
        messages.error(request, _('An error occurred while processing your IPSuite4 account.'))
    return redirect("services:services")
