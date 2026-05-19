from datetime import datetime

from django.db import models
from django.utils import timezone

from allianceauth.eveonline.models import EveCharacter


class OpTimerType(models.Model):
    type = models.CharField(max_length=254, default="")

    class Meta:
        ordering = ["type"]
        default_permissions = ()

    def __str__(self) -> str:
        return self.type


class OpTimer(models.Model):
    doctrine = models.CharField(max_length=254, default="")
    system = models.CharField(max_length=254, default="")
    start = models.DateTimeField(default=datetime.now)
    duration = models.CharField(max_length=25, default="")
    operation_name = models.CharField(max_length=254, default="")
    fc = models.CharField(max_length=254, default="")
    post_time = models.DateTimeField(default=timezone.now)
    eve_character = models.ForeignKey(EveCharacter, null=True, on_delete=models.SET_NULL)
    description = models.TextField(blank=True, default="")
    type = models.ForeignKey(OpTimerType, null=True, on_delete=models.SET_NULL)

    class Meta:
        ordering = ["start"]
        default_permissions = ()
        # Intentionally Commented out
        # AAv0 has these in the Auth_ Content Type
        # permissions = (
        #     ('optimer_view', 'optimer_view'),
        #     ('optimer_management', 'optimer_management'),
        # )

    def __str__(self) -> str:
        return self.operation_name
