"""Resolve buyback pricing tier for a user or anonymous public visitor."""

from __future__ import annotations

from django.contrib.auth.models import AnonymousUser, User

from buyback_v2.context import PricingContext
from buyback_v2.models import EntityType, PricingTier, ProgramPricingProfile


def _affiliation_ids(user: User) -> tuple[set[int], set[int], set[int]]:
    corp_ids: set[int] = set()
    alliance_ids: set[int] = set()
    character_ids: set[int] = set()
    if not user.is_authenticated:
        return corp_ids, alliance_ids, character_ids

    try:
        profile = user.profile
    except Exception:
        profile = None

    if profile and profile.main_character_id:
        from allianceauth.eveonline.models import EveCharacter

        mc = EveCharacter.objects.filter(pk=profile.main_character_id).first()
        if mc:
            character_ids.add(int(mc.character_id))
            if mc.corporation_id:
                corp_ids.add(int(mc.corporation_id))
            if mc.alliance_id:
                alliance_ids.add(int(mc.alliance_id))

    from allianceauth.eveonline.models import EveCharacter

    for char_id, corp_id, alliance_id in (
        EveCharacter.objects.filter(character_ownership__user_id=user.pk)
        .values_list("character_id", "corporation_id", "alliance_id")
        .distinct()
    ):
        character_ids.add(int(char_id))
        if corp_id:
            corp_ids.add(int(corp_id))
        if alliance_id:
            alliance_ids.add(int(alliance_id))

    return corp_ids, alliance_ids, character_ids


def resolve_pricing_context(
    *,
    program,
    user: User | AnonymousUser | None,
    force_public: bool = False,
) -> PricingContext:
    try:
        profile = program.pricing_v2
    except ProgramPricingProfile.DoesNotExist:
        return PricingContext(
            multiplier=1.0,
            tier_name="Standard",
            tier_id=None,
            is_public=bool(force_public),
        )

    if force_public or not user or not user.is_authenticated:
        return _resolve_public_context(profile)

    corp_ids, alliance_ids, character_ids = _affiliation_ids(user)
    matched = _match_tier(
        profile, corp_ids, alliance_ids, character_ids, public_only=False
    )
    if matched:
        return PricingContext(
            multiplier=float(matched.multiplier),
            tier_name=matched.name,
            tier_id=matched.pk,
            is_public=False,
            corp_id=next(iter(corp_ids), None),
            alliance_id=next(iter(alliance_ids), None),
        )

    default = (
        PricingTier.objects.filter(program_profile=profile, is_default=True, is_public=False)
        .order_by("-priority")
        .first()
    )
    if default:
        return PricingContext(
            multiplier=float(default.multiplier),
            tier_name=default.name,
            tier_id=default.pk,
            is_public=False,
        )

    return PricingContext(
        multiplier=1.0,
        tier_name="Standard",
        tier_id=None,
        is_public=False,
        corp_id=next(iter(corp_ids), None) if corp_ids else None,
        alliance_id=next(iter(alliance_ids), None) if alliance_ids else None,
    )


def _resolve_public_context(profile: ProgramPricingProfile) -> PricingContext:
    if not profile.public_calculator_enabled:
        return PricingContext(
            multiplier=1.0,
            tier_name="Unavailable",
            tier_id=None,
            is_public=True,
        )

    public_tier = (
        PricingTier.objects.filter(program_profile=profile, is_public=True)
        .order_by("-priority", "id")
        .first()
    )
    if public_tier:
        return PricingContext(
            multiplier=float(public_tier.multiplier),
            tier_name=public_tier.name,
            tier_id=public_tier.pk,
            is_public=True,
        )

    return PricingContext(
        multiplier=float(profile.public_multiplier),
        tier_name="Public",
        tier_id=None,
        is_public=True,
    )


def _match_tier(
    profile: ProgramPricingProfile,
    corp_ids: set[int],
    alliance_ids: set[int],
    character_ids: set[int],
    *,
    public_only: bool,
) -> PricingTier | None:
    qs = PricingTier.objects.filter(program_profile=profile).prefetch_related("rules")
    if public_only:
        qs = qs.filter(is_public=True)
    else:
        qs = qs.filter(is_public=False)

    for tier in qs.order_by("-priority", "id"):
        for rule in tier.rules.all():
            if rule.entity_type == EntityType.CORPORATION and rule.entity_id in corp_ids:
                return tier
            if rule.entity_type == EntityType.ALLIANCE and rule.entity_id in alliance_ids:
                return tier
            if rule.entity_type == EntityType.CHARACTER and rule.entity_id in character_ids:
                return tier
    return None
