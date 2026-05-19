from django.contrib.auth.models import User
from django.db import models


class Ips4User(models.Model):
    user = models.OneToOneField(User, primary_key=True, on_delete=models.CASCADE, related_name="ips4")
    username = models.CharField(max_length=254)
    id = models.CharField(max_length=254)

    class Meta:
        default_permissions = ()
        permissions = (("access_ips4", "Can access the IPS4 service"),)

    def __str__(self) -> str:
        return self.username
