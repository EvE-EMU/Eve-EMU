from django.http import Http404
from django.shortcuts import get_object_or_404, render
from django.utils.translation import gettext_lazy as _

from buybackprogram.models import Program

from buyback_v2.calculator import run_calculator
from buyback_v2.context import pricing_context
from buyback_v2.forms import PublicCalculatorForm
from buyback_v2.models import ProgramPricingProfile
from buyback_v2.tiers import resolve_pricing_context


def _programs_public_qs():
    return (
        Program.objects.filter(pricing_v2__public_calculator_enabled=True)
        .select_related("pricing_v2", "owner")
        .prefetch_related("location")
        .distinct()
    )


def public_index(request):
    programs = _programs_public_qs()
    return render(
        request,
        "buyback_v2/public_index.html",
        {"programs": programs, "title": _("Public buyback calculator")},
    )


def public_program_calculate(request, program_pk: int):
    program = get_object_or_404(Program, pk=program_pk)
    try:
        profile = program.pricing_v2
    except ProgramPricingProfile.DoesNotExist:
        raise Http404 from None
    if not profile.public_calculator_enabled:
        raise Http404

    ctx = resolve_pricing_context(program=program, user=None, force_public=True)
    result = None
    form = PublicCalculatorForm()

    if request.method == "POST":
        form = PublicCalculatorForm(request.POST)
        if form.is_valid():
            with pricing_context(ctx):
                result = run_calculator(
                    program=program,
                    items_text=form.cleaned_data["items"],
                    donation=int(form.cleaned_data.get("donation") or 0),
                )

    return render(
        request,
        "buyback_v2/public_calculate.html",
        {
            "program": program,
            "form": form,
            "result": result,
            "pricing_ctx": ctx,
            "title": _("Public buyback calculator"),
        },
    )


def tier_preview(request, program_pk: int):
    """Logged-in users can see which tier applies before using the main calculator."""
    program = get_object_or_404(Program, pk=program_pk)
    ctx = resolve_pricing_context(program=program, user=request.user)
    return render(
        request,
        "buyback_v2/tier_preview.html",
        {"program": program, "pricing_ctx": ctx},
    )
