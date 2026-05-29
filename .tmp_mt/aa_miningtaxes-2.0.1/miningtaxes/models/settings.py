# Shamelessly stolen from Member Audit
from django.db import models

from allianceauth.services.hooks import get_extension_logger
from app_utils.logging import LoggerAddTag

from .. import __title__

logger = LoggerAddTag(get_extension_logger(__name__), __title__)


class Settings(models.Model):
    phrase = models.CharField(
        verbose_name="Keyword (case insensitive) that must be present in the donation reason to be counted. Leave blank/empty to count all donations regardless of reason.",
        max_length=10,
        default="",
        blank=True,
    )
    interest_rate = models.FloatField(
        verbose_name="Monthly interest rate (%) if taxes have not been paid",
        default=5.0,
        null=False,
    )

    def save(self, *args, **kwargs):
        self.pk = 1
        super(Settings, self).save(*args, **kwargs)

    def delete(self, *args, **kwargs):
        pass

    @classmethod
    def load(cls):
        obj, _ = cls.objects.get_or_create(pk=1)
        return obj
