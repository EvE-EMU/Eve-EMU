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


class PenguinWhMap(models.Model):
    """One shared wormhole chain, stored as a single JSON blob.

    Keyed by (scope, key): scope in {personal, corp, alliance}; key is the AA
    user pk for a personal map, else the corp / alliance id. `rev` bumps on
    every write so the desktop client can do optimistic-concurrency merges
    instead of locking.
    """

    scope = models.CharField(max_length=10, default="personal", db_index=True)
    key = models.BigIntegerField(default=0, db_index=True)
    data = models.JSONField(default=dict)
    rev = models.BigIntegerField(default=0)
    updated_by = models.CharField(max_length=100, blank=True, default="")
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        app_label = "penguin_bridge"
        unique_together = [("scope", "key")]

    def as_dict(self) -> dict:
        return {
            "scope": self.scope,
            "key": self.key,
            "data": self.data or {},
            "rev": self.rev,
            "updated_by": self.updated_by,
            "updated_at": self.updated_at.isoformat() if self.updated_at else "",
        }


class PenguinPing(models.Model):
    """A fleet ping / timer shared to a corp or alliance.

    Posted by a signed-in user (to their own corp / alliance) or by a relay
    forwarder that presents the shared secret. Read by every client in that
    corp / alliance until it expires.
    """

    CORP = "corp"
    ALLIANCE = "alliance"
    SCOPE_CHOICES = [(CORP, "Corp"), (ALLIANCE, "Alliance")]

    scope = models.CharField(max_length=10, choices=SCOPE_CHOICES, db_index=True)
    key = models.BigIntegerField(db_index=True)  # corp or alliance id
    kind = models.CharField(max_length=16, default="misc")  # fc/formup/doctrine/undock/timer/misc
    text = models.TextField()
    system = models.CharField(max_length=64, blank=True, default="")
    at_unix = models.BigIntegerField(default=0)  # timer target, 0 = none
    author = models.CharField(max_length=100, blank=True, default="")
    created_at = models.DateTimeField(auto_now_add=True, db_index=True)
    expires_at = models.DateTimeField(db_index=True)

    class Meta:
        app_label = "penguin_bridge"
        ordering = ["-created_at", "-id"]

    def as_dict(self) -> dict:
        return {
            "id": self.id,
            "scope": self.scope,
            "kind": self.kind,
            "text": self.text,
            "system": self.system,
            "at_unix": self.at_unix,
            "author": self.author,
            "created_at": self.created_at.isoformat() if self.created_at else "",
            "expires_at": self.expires_at.isoformat() if self.expires_at else "",
        }


class PenguinPingChannel(models.Model):
    """Maps a Discord channel to a EVE-Penguin ping target.

    The Discord relay cog forwards each new message in `discord_channel_id` to
    `/penguin/pings` as `(scope, key, kind)` with `label` as a prefix. Only
    clients whose main is in that corp / alliance ever see it — that is the
    "does this user have access to the channel" gate, at org granularity.
    """

    discord_channel_id = models.BigIntegerField(unique=True, db_index=True)
    label = models.CharField(max_length=40, blank=True, default="")
    scope = models.CharField(max_length=10, default="alliance")  # corp | alliance
    key = models.BigIntegerField()  # corp or alliance id
    kind = models.CharField(max_length=16, default="misc")
    ttl_hours = models.PositiveIntegerField(default=6)
    enabled = models.BooleanField(default=True)

    class Meta:
        app_label = "penguin_bridge"

    def __str__(self) -> str:  # pragma: no cover
        return f"{self.discord_channel_id} → {self.scope}:{self.key} ({self.label})"
