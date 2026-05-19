"""
Admin classes for custom_css app
"""

# Django
# Django Solos
from solo.admin import SingletonModelAdmin

from django.contrib import admin

from allianceauth.custom_css.forms import CustomCSSAdminForm

# Alliance Auth Custom CSS
from allianceauth.custom_css.models import CustomCSS


@admin.register(CustomCSS)
class CustomCSSAdmin(SingletonModelAdmin):
    """
    Custom CSS Admin
    """

    form = CustomCSSAdminForm

    # Leave this here for when we decide to add syntax highlighting to the CSS editor
    # change_form_template = 'custom_css/admin/change_form.html'
