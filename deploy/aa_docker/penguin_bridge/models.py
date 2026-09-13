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


class PenguinBuildJob(models.Model):
    """A corp-project or divisional-manufacturing build job — EVE-Penguin's
    own model (not Auth Indy Hub's `ProductionProject`, which the desktop
    client's *solo* mode already uses directly): those are personal, this is
    a shared, org-scoped board with claim/deliver tracking, the divisional
    D0-D3 tier a solo project has no concept of, and a manager/line-member
    split solo mode doesn't need either.

    The desktop client computes and owns the actual cost/margin numbers
    (verified against the same real CCP formulas the solo calculator uses)
    — `corp_profit_margin_pct`/`*_share_isk` are just where it stores the
    result, not something this backend derives on its own.
    """

    MODE_CHOICES = [
        ("corp", "Corp Project"),
        ("divisional", "Divisional Manufacturing"),
    ]
    TIER_CHOICES = [
        ("d0", "D0 — quick builds"),
        ("d1", "D1 — capital components"),
        ("d2", "D2 — T2 / advanced components"),
        ("d3", "D3 — final builds"),
    ]
    STATUS_CHOICES = [
        ("open", "Open"),
        ("claimed", "Claimed"),
        ("in_progress", "In progress"),
        ("delivered", "Delivered"),
        ("cancelled", "Cancelled"),
    ]
    SOURCE_CHOICES = [
        ("manual", "Manual"),
        ("fit", "From a fit"),
        ("auto_restock", "Auto-restock (corp minimum)"),
    ]

    owner_user_id = models.BigIntegerField(db_index=True)
    owner_name = models.CharField(max_length=100, blank=True, default="")
    corp_id = models.BigIntegerField(default=0, db_index=True)
    alliance_id = models.BigIntegerField(default=0, db_index=True)

    mode = models.CharField(max_length=16, choices=MODE_CHOICES, default="corp", db_index=True)
    tier = models.CharField(max_length=4, choices=TIER_CHOICES, default="d0", db_index=True)
    status = models.CharField(max_length=16, choices=STATUS_CHOICES, default="open", db_index=True)

    type_id = models.IntegerField(default=0)
    type_name = models.CharField(max_length=255)
    quantity = models.BigIntegerField(default=1)
    blueprint_type_id = models.IntegerField(null=True, blank=True)

    source_kind = models.CharField(max_length=16, choices=SOURCE_CHOICES, default="manual")
    source_ref = models.CharField(max_length=255, blank=True, default="")

    notes = models.TextField(blank=True, default="")
    metadata = models.JSONField(default=dict, blank=True)

    corp_profit_margin_pct = models.DecimalField(max_digits=6, decimal_places=2, default=0)
    builder_share_isk = models.DecimalField(max_digits=18, decimal_places=2, null=True, blank=True)
    corp_share_isk = models.DecimalField(max_digits=18, decimal_places=2, null=True, blank=True)

    claimed_by_user_id = models.BigIntegerField(null=True, blank=True, db_index=True)
    claimed_by_name = models.CharField(max_length=100, blank=True, default="")
    claimed_at = models.DateTimeField(null=True, blank=True)
    expected_delivery_at = models.DateTimeField(null=True, blank=True)
    delivered_at = models.DateTimeField(null=True, blank=True)

    created_at = models.DateTimeField(auto_now_add=True, db_index=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        app_label = "penguin_bridge"
        ordering = ["-created_at", "-id"]
        default_permissions = ()
        permissions = [
            ("can_manage_build_jobs", "Can create/manage corp and divisional build jobs"),
        ]
        indexes = [
            models.Index(fields=["corp_id", "mode", "tier", "status"]),
            models.Index(fields=["alliance_id", "mode", "tier", "status"]),
            models.Index(fields=["claimed_by_user_id", "status"]),
        ]

    def __str__(self) -> str:  # pragma: no cover
        return f"{self.get_mode_display()} [{self.tier}] {self.type_name} x{self.quantity} ({self.status})"

    def as_dict(self) -> dict:
        return {
            "id": self.id,
            "owner_name": self.owner_name,
            "corp_id": self.corp_id,
            "alliance_id": self.alliance_id,
            "mode": self.mode,
            "tier": self.tier,
            "status": self.status,
            "type_id": self.type_id,
            "type_name": self.type_name,
            "quantity": self.quantity,
            "blueprint_type_id": self.blueprint_type_id,
            "source_kind": self.source_kind,
            "source_ref": self.source_ref,
            "notes": self.notes,
            "metadata": self.metadata or {},
            "corp_profit_margin_pct": float(self.corp_profit_margin_pct or 0),
            "builder_share_isk": float(self.builder_share_isk) if self.builder_share_isk is not None else None,
            "corp_share_isk": float(self.corp_share_isk) if self.corp_share_isk is not None else None,
            "claimed_by_name": self.claimed_by_name,
            "claimed_at": self.claimed_at.isoformat() if self.claimed_at else None,
            "expected_delivery_at": self.expected_delivery_at.isoformat() if self.expected_delivery_at else None,
            "delivered_at": self.delivered_at.isoformat() if self.delivered_at else None,
            "created_at": self.created_at.isoformat(),
            "updated_at": self.updated_at.isoformat(),
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
