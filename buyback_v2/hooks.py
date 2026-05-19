"""Monkey-patch aa-buybackprogram pricing for enabled v2 programs."""

from __future__ import annotations

from functools import wraps

from buyback_v2.context import pricing_context
from buyback_v2.models import PriceBasis, ProgramPricingProfile
from buyback_v2.pricing import (
    effective_price_basis,
    ensure_janice_item_price,
    ensure_material_prices,
    recompute_item_values,
)
from buyback_v2.tiers import resolve_pricing_context

_INSTALLED = False


def get_profile(program) -> ProgramPricingProfile | None:
    try:
        return program.pricing_v2
    except ProgramPricingProfile.DoesNotExist:
        return None


def install_buyback_v2_hooks() -> None:
    global _INSTALLED
    if _INSTALLED:
        return

    import buybackprogram.helpers as helpers
    from buybackprogram.views import calculate as calculate_views

    _orig_get_item_prices = helpers.get_item_prices
    _orig_get_item_values = helpers.get_item_values
    _orig_program_calculate = calculate_views.program_calculate

    def get_item_prices(item_type, name, quantity, program):
        profile = get_profile(program)
        old_refined = None
        if profile and profile.enabled and profile.reprocess_non_ore:
            old_refined = program.use_refined_value
            program.use_refined_value = True

        try:
            prices = _orig_get_item_prices(item_type, name, quantity, program)
            if profile and profile.enabled and profile.reprocess_non_ore:
                prices = ensure_material_prices(item_type, name, quantity, program, prices)
            return prices
        finally:
            if old_refined is not None:
                program.use_refined_value = old_refined

    def get_item_values(item_type, item_prices, program):
        profile = get_profile(program)
        if not profile or not profile.enabled:
            return _orig_get_item_values(item_type, item_prices, program)

        old_price_type = None
        if profile.price_basis != PriceBasis.PROGRAM:
            old_price_type = program.price_type
            program.price_type = effective_price_basis(profile, program)

        if profile.force_janice_prices:
            ensure_janice_item_price(item_type.id, force=True)

        try:
            values = _orig_get_item_values(item_type, item_prices, program)
            if item_prices.get("npc_prices"):
                from buyback_v2.pricing import apply_tier_multiplier

                return apply_tier_multiplier(values)
            return recompute_item_values(values, item_prices, program, profile)
        finally:
            if old_price_type is not None:
                program.price_type = old_price_type

    @wraps(_orig_program_calculate)
    def program_calculate(request, program_pk):
        program = calculate_views.Program.objects.filter(pk=program_pk).first()
        if program is None:
            return _orig_program_calculate(request, program_pk)

        ctx = resolve_pricing_context(program=program, user=request.user)
        request.buyback_pricing_ctx = ctx
        with pricing_context(ctx):
            return _orig_program_calculate(request, program_pk)

    helpers.get_item_prices = get_item_prices
    helpers.get_item_values = get_item_values
    calculate_views.program_calculate = program_calculate
    _INSTALLED = True
