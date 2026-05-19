from django.db import models


class SmfUser(models.Model):
    user = models.OneToOneField("auth.User", primary_key=True, on_delete=models.CASCADE, related_name="smf")
    username = models.CharField(max_length=254)

    class Meta:
        default_permissions = ()
        permissions = (("access_smf", "Can access the SMF service"),)

    def __str__(self) -> str:
        return self.username
