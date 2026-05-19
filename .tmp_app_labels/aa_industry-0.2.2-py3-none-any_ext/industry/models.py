from allianceauth.authentication.models import CharacterOwnership
from allianceauth.eveonline.models import EveCharacter
from django.db import models
from django.contrib.auth import get_user_model

from django.utils.translation import gettext as _
from eveuniverse.models import EveSolarSystem

User = get_user_model()


class Industry(models.Model):
    pass


class UserCharacters(models.Model):
    user = models.ForeignKey(User, blank=False, on_delete=models.CASCADE)
    character_ownership = models.OneToOneField(
        CharacterOwnership,
        related_name="industry_character",
        on_delete=models.CASCADE,
        primary_key=True,
        help_text="ownership of this character on Auth",
    )

    def __str__(self):
        return f'{self.user.profile.main_character} - {self.character_ownership.character}'

    class Meta:
        ordering = ['user']
        verbose_name = _('User x Characters')
        verbose_name_plural = _('User x Characters')


class Facility(models.Model):
    facility_id = models.BigIntegerField(_('Facility'), null=False, blank=False)
    name = models.CharField(_('Name'), null=False, blank=False, max_length=2048)
    owner_id = models.BigIntegerField(_('Owner Id'), null=False, blank=False)
    solar_system = models.ForeignKey(EveSolarSystem, null=True, blank=True, on_delete=models.CASCADE)
    type_id = models.BigIntegerField(_('Type'), null=False, blank=False)

    class Meta:
        ordering = ['name']
        verbose_name = _('Facility')
        verbose_name_plural = _('Facilities')
