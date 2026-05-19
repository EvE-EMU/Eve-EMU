"""Validators for Blueprints."""

from django.core.exceptions import ValidationError
from django.utils.translation import gettext_lazy as _


def validate_material_efficiency(value):
    """Raise error if a given value is not valid as material efficiency."""
    if value > 10 or value < 0:
        raise ValidationError(_("%s is not a valid material efficiency") % value)


def validate_time_efficiency(value):
    """Raise error if a given value is not valid as time efficiency."""
    if value % 2 != 0 or value > 20 or value < 0:
        raise ValidationError(_("%s is not a valid time efficiency") % value)
