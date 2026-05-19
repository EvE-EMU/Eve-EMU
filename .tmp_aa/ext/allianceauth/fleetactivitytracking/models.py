from django.contrib.auth.models import User
from django.db import models
from django.utils import timezone

from allianceauth.eveonline.models import EveCharacter
from allianceauth.framework.api.user import get_sentinel_user


class Fatlink(models.Model):
    fatdatetime = models.DateTimeField(default=timezone.now)
    duration = models.PositiveIntegerField()
    fleet = models.CharField(max_length=254)
    hash = models.CharField(max_length=254, unique=True)
    creator = models.ForeignKey(User, on_delete=models.SET(get_sentinel_user))

    class Meta:
        permissions = (
            # Intentionally Commented out
            # AAv0 has these in the Auth_ Content Type
            # ('fleetactivitytracking', 'fleetactivitytracking'),
            # ('fleetactivitytracking_statistics', 'fleetactivitytracking_statistics'),
        )

    def __str__(self) -> str:
        return self.fleet


class Fat(models.Model):
    character = models.ForeignKey(EveCharacter, on_delete=models.CASCADE)
    fatlink = models.ForeignKey(Fatlink, on_delete=models.CASCADE)
    system = models.CharField(max_length=30)
    shiptype = models.CharField(max_length=100)
    station = models.CharField(max_length=125)
    user = models.ForeignKey(User, on_delete=models.CASCADE)

    class Meta:
        default_permissions = ()
        unique_together = (("character", "fatlink"),)

    def __str__(self) -> str:
        return f"Fat-link for {self.character.character_name}"
