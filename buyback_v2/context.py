"""Request-scoped pricing tier (corp / alliance / public multipliers)."""

from __future__ import annotations

from contextlib import contextmanager
from contextvars import ContextVar
from dataclasses import dataclass

_pricing_context: ContextVar[PricingContext | None] = ContextVar(
    "buyback_v2_pricing_context", default=None
)


@dataclass(frozen=True)
class PricingContext:
    multiplier: float
    tier_name: str
    tier_id: int | None
    is_public: bool
    corp_id: int | None = None
    alliance_id: int | None = None


def get_pricing_context() -> PricingContext | None:
    return _pricing_context.get()


def set_pricing_context(ctx: PricingContext | None) -> None:
    _pricing_context.set(ctx)


@contextmanager
def pricing_context(ctx: PricingContext | None):
    token = _pricing_context.set(ctx)
    try:
        yield ctx
    finally:
        _pricing_context.reset(token)
