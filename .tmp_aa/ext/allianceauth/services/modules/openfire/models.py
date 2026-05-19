from django.db import models


class OpenfireUser(models.Model):
    user = models.OneToOneField("auth.User", primary_key=True, on_delete=models.CASCADE, related_name="openfire")
    username = models.CharField(max_length=254)

    class Meta:
        default_permissions = ()
        permissions = (
            ("access_openfire", "Can access the Openfire service"),
            # Intentionally Commented out
            # AAv0 has these in the Auth_ Content Type
            # ('jabber_broadcast', 'jabber_broadcast'),
            # ('jabber_broadcast_all', 'jabber_broadcast_all'),
        )

    def __str__(self) -> str:
        return self.username
