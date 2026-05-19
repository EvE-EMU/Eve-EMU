from django.db import models


class Log(models.Model):
    """
    No relationships just a log.
    """

    user = models.TextField(default="", blank=True, null=True)

    action = models.TextField(default="", blank=True, null=True)

    details = models.TextField(default="", blank=True, null=True)

    created = models.DateTimeField(auto_now_add=True)
