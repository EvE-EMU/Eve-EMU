import logging

from django.contrib import messages
from django.contrib.auth.decorators import login_required, permission_required
from django.shortcuts import redirect, render
from django.utils.translation import gettext_lazy as _

from allianceauth.services.forms import ServicePasswordForm

from .manager import XenForoManager
from .models import XenforoUser
from .tasks import XenforoTasks

logger = logging.getLogger(__name__)

ACCESS_PERM = 'xenforo.access_xenforo'


@login_required
@permission_required(ACCESS_PERM)
def activate_xenforo_forum(request):
    logger.debug(f"activate_xenforo_forum called by user {request.user}")
    character = request.user.profile.main_character
    logger.debug(f"Adding XenForo user for user {request.user} with main character {character}")
    result = XenForoManager.add_user(XenforoTasks.get_username(request.user), request.user.email)
    # Based on XenAPI's response codes
    if result['response']['status_code'] == 200:
        XenforoUser.objects.update_or_create(user=request.user, defaults={'username': result['username']})
        logger.info(f"Updated user {request.user} with XenForo credentials. Updating groups.")
        messages.success(request, _('Activated XenForo account.'))
        credentials = {
            'username': result['username'],
            'password': result['password'],
        }
        return render(request, 'services/service_credentials.html',
                        context={'credentials': credentials, 'service': 'XenForo'})

    else:
        logger.error(f"Unsuccessful attempt to activate XenForo for user {request.user}")
        messages.error(request, _('An error occurred while processing your XenForo account.'))
    return redirect("services:services")


@login_required
@permission_required(ACCESS_PERM)
def deactivate_xenforo_forum(request):
    logger.debug(f"deactivate_xenforo_forum called by user {request.user}")
    if XenforoTasks.delete_user(request.user):
        logger.info(f"Successfully deactivated XenForo for user {request.user}")
        messages.success(request, _('Deactivated XenForo account.'))
    else:
        messages.error(request, _('An error occurred while processing your XenForo account.'))
    return redirect("services:services")


@login_required
@permission_required(ACCESS_PERM)
def reset_xenforo_password(request):
    logger.debug(f"reset_xenforo_password called by user {request.user}")
    if XenforoTasks.has_account(request.user):
        result = XenForoManager.reset_password(request.user.xenforo.username)
        # Based on XenAPI's response codes
        if result['response']['status_code'] == 200:
            logger.info(f"Successfully reset XenForo password for user {request.user}")
            messages.success(request, _('Reset XenForo account password.'))
            credentials = {
                'username': request.user.xenforo.username,
                'password': result['password'],
            }
            return render(request, 'services/service_credentials.html',
                        context={'credentials': credentials, 'service': 'XenForo'})
    logger.error(f"Unsuccessful attempt to reset XenForo password for user {request.user}")
    messages.error(request, _('An error occurred while processing your XenForo account.'))
    return redirect("services:services")


@login_required
@permission_required(ACCESS_PERM)
def set_xenforo_password(request):
    logger.debug(f"set_xenforo_password called by user {request.user}")
    if request.method == 'POST':
        logger.debug("Received POST request with form.")
        form = ServicePasswordForm(request.POST)
        logger.debug(f"Form is valid: {form.is_valid()}")
        if form.is_valid() and XenforoTasks.has_account(request.user):
            password = form.cleaned_data['password']
            logger.debug(f"Form contains password of length {len(password)}")
            result = XenForoManager.update_user_password(request.user.xenforo.username, password)
            if result['response']['status_code'] == 200:
                logger.info(f"Successfully reset XenForo password for user {request.user}")
                messages.success(request, _('Changed XenForo password.'))
            else:
                logger.error(f"Failed to install custom XenForo password for user {request.user}")
                messages.error(request, _('An error occurred while processing your XenForo account.'))
            return redirect('services:services')
    else:
        logger.debug("Request is not type POST - providing empty form.")
        form = ServicePasswordForm()

    logger.debug(f"Rendering form for user {request.user}")
    context = {'form': form, 'service': 'Forum'}
    return render(request, 'services/service_password.html', context=context)
