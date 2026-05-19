from django.contrib import admin

from standing_fleet_tracker.models import (
    CharacterMonthlyKPI,
    CharacterScore,
    FleetKillmail,
    FleetLocationSample,
    FleetPulse,
    FleetPulseMember,
    FleetSession,
    FleetSessionShipLog,
    MiningLedgerEntry,
    PointLedger,
    ShipFitSnapshot,
    ShipFleetStat,
    StandingFleetAllowlist,
    SovSystemCache,
    WalletJournalEntry,
)


@admin.register(FleetSession)
class FleetSessionAdmin(admin.ModelAdmin):
    list_display = (
        "character",
        "fleet_id",
        "is_standing_fleet",
        "classification",
        "started_at",
        "ended_at",
    )
    list_filter = ("is_standing_fleet", "classification")
    search_fields = ("character__character_name", "fleet_id")


@admin.register(PointLedger)
class PointLedgerAdmin(admin.ModelAdmin):
    list_display = ("user", "character", "event_type", "points", "created_at")
    list_filter = ("event_type",)
    search_fields = ("user__username", "character__character_name")


class FleetPulseMemberInline(admin.TabularInline):
    model = FleetPulseMember
    extra = 0
    readonly_fields = (
        "eve_character_id",
        "character",
        "role",
        "pulse_points_awarded",
        "join_time",
    )


@admin.register(FleetPulse)
class FleetPulseAdmin(admin.ModelAdmin):
    list_display = (
        "fleet_id",
        "pulsed_at",
        "member_count",
        "is_standing_fleet",
        "members_source",
        "polled_by",
    )
    list_filter = ("is_standing_fleet", "members_source")
    inlines = [FleetPulseMemberInline]


@admin.register(CharacterScore)
class CharacterScoreAdmin(admin.ModelAdmin):
    list_display = (
        "character",
        "total_points",
        "standing_fleet_hours",
        "pulse_points",
        "penalty_hours",
        "kill_bonus_points",
        "last_polled_at",
    )
    search_fields = ("character__character_name",)


admin.site.register(FleetLocationSample)
admin.site.register(FleetSessionShipLog)
admin.site.register(FleetKillmail)
admin.site.register(ShipFleetStat)
admin.site.register(StandingFleetAllowlist)
admin.site.register(SovSystemCache)


@admin.register(ShipFitSnapshot)
class ShipFitSnapshotAdmin(admin.ModelAdmin):
    list_display = ("character", "ship_name", "ship_type_id", "session", "in_standing_fleet", "recorded_at")
    list_filter = ("in_standing_fleet",)
    search_fields = ("character__character_name", "ship_name")
    readonly_fields = ("modules_json", "modules_fingerprint", "eft_text")


@admin.register(CharacterMonthlyKPI)
class CharacterMonthlyKPIAdmin(admin.ModelAdmin):
    list_display = (
        "character",
        "year",
        "month",
        "avg_ship_group_name",
        "avg_region_name",
        "pct_standing_fleet",
        "computed_at",
    )
    list_filter = ("year", "month")


admin.site.register(WalletJournalEntry)
admin.site.register(MiningLedgerEntry)
