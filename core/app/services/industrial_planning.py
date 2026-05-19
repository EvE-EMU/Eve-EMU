"""Coalition industrial planning helpers (stateless; persist in Django ``industry_suite`` or AA DB)."""

from __future__ import annotations

from pydantic import BaseModel, Field, model_validator

# ESI (implement with esi-client-python / django-eveuniverse in Celery workers):
# - GET /corporations/{corporation_id}/industry/jobs/ — esi-industry.read_corporation_jobs.v1
# - Corporation industry "projects" Data Hub routes — follow the official API explorer for current paths.


class MassBuildLine(BaseModel):
    """One line item on a corp/coalition build sheet."""

    type_id: int = Field(..., ge=1)
    quantity: int = Field(..., ge=1)
    label: str | None = Field(None, max_length=256)

    @model_validator(mode="after")
    def _default_label(self) -> MassBuildLine:
        if not (self.label or "").strip():
            object.__setattr__(self, "label", f"type {self.type_id}")
        return self


class SplitMassBuildIn(BaseModel):
    """Request body for splitting a massive build into sub-orders."""

    corporation_id: int = Field(..., ge=1, description="EVE corporation id owning the project context.")
    lines: list[MassBuildLine] = Field(..., min_length=1)
    max_units_per_suborder: int = Field(5_000, ge=1, le=500_000)


class SubOrderPlan(BaseModel):
    label: str
    type_id: int
    quantity: int


def split_mass_build(payload: SplitMassBuildIn) -> list[SubOrderPlan]:
    """Split each line into ≤ ``max_units_per_suborder`` chunks (simple greedy split)."""
    out: list[SubOrderPlan] = []
    cap = payload.max_units_per_suborder
    for line in payload.lines:
        remaining = line.quantity
        base = (line.label or f"type {line.type_id}").strip() or f"type {line.type_id}"
        part = 0
        while remaining > 0:
            chunk = min(cap, remaining)
            part += 1
            label = base if remaining <= cap and part == 1 else f"{base} (part {part})"
            out.append(SubOrderPlan(label=label[:256], type_id=line.type_id, quantity=chunk))
            remaining -= chunk
    return out
