"""Runtime fixes for aa-metenox on minimal / lagging eveuniverse loads."""

from __future__ import annotations


def patch_metenox_for_runtime() -> None:
    """Avoid 500s when Magmatic Gas (type 81143) is missing from the local SDE copy."""
    try:
        from eveuniverse.models import EveType
        from metenox.models import EveTypePrice
    except Exception:
        return

    _orig = EveTypePrice.get_magmatic_gases_price

    @classmethod  # type: ignore[misc]
    def _safe_magmatic_gases_price(cls):  # noqa: ANN001
        try:
            return _orig.__func__(cls)
        except EveType.DoesNotExist:
            return 0.0

    EveTypePrice.get_magmatic_gases_price = _safe_magmatic_gases_price  # type: ignore[method-assign]
