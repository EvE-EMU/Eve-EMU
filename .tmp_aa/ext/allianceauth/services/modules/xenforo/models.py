from django.db import models


class XenforoUser(models.Model):
    user = models.OneToOneField("auth.User", primary_key=True, on_delete=models.CASCADE, related_name="xenforo")
    username = models.CharField(max_length=254)

    class Meta:
        default_permissions = ()
        permissions = (("access_xenforo", "Can access the XenForo service"),)

    def __str__(self) -> str:
        return self.username
