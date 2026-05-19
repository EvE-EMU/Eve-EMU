from django.db import models


class Phpbb3User(models.Model):
    user = models.OneToOneField("auth.User", primary_key=True, on_delete=models.CASCADE, related_name="phpbb3")
    username = models.CharField(max_length=254)

    class Meta:
        default_permissions = ()
        permissions = (("access_phpbb3", "Can access the phpBB3 service"),)

    def __str__(self) -> str:
        return self.username
