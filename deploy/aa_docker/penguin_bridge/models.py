"""EVE-Penguin bridge models.

Only the shared fitting store lives here — the session is stateless (session.py)
and ESI is proxied live. Adding this app to a running deployment therefore needs
one migration:

    docker compose exec aa-web python manage.py migrate penguin_bridge
"""

from __future__ import annotations

from django.db import models


class PenguinFitting(models.Model):
    """A doctrine / saved fitting, shared at private / corp / alliance scope.

    Ownership is by AA user id (not character) so a fit follows the account.
    Corp / alliance visibility is by the id stored here; the API only lets a
    user write a scope for an org they actually belong to, and lists a fit to
    others by matching their own corp / alliance ids.
    """

    PRIVATE = "private"
    CORP = "corp"
    ALLIANCE = "alliance"
    SCOPE_CHOICES = [
        (PRIVATE, "Private"),
        (CORP, "Corp"),
        (ALLIANCE, "Alliance"),
    ]

    owner_user_id = models.BigIntegerField(db_index=True)
    owner_name = models.CharField(max_length=100, blank=True, default="")
    name = models.CharField(max_length=120)
    ship_type_id = models.IntegerField(default=0)
    eft = models.TextField()
    scope = models.CharField(
        max_length=10, choices=SCOPE_CHOICES, default=PRIVATE, db_index=True
    )
    corp_id = models.BigIntegerField(default=0, db_index=True)
    alliance_id = models.BigIntegerField(default=0, db_index=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        app_label = "penguin_bridge"
        ordering = ["name", "id"]

    def __str__(self) -> str:  # pragma: no cover
        return f"{self.name} ({self.scope})"

    def as_dict(self, *, mine: bool) -> dict:
        return {
            "id": self.id,
            "name": self.name,
            "ship_type_id": self.ship_type_id,
            "eft": self.eft,
            "scope": self.scope,
            "corp_id": self.corp_id,
            "alliance_id": self.alliance_id,
            "owner_name": self.owner_name,
            "mine": mine,
            "updated": self.updated_at.isoformat(),
        }
