from __future__ import annotations

from decimal import Decimal

from django.contrib import messages
from django.contrib.auth.decorators import login_required, permission_required
from django.http import HttpRequest, HttpResponse, HttpResponseForbidden, JsonResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.views.decorators.http import require_http_methods

from corp_orders.constants import SPEED_DESCRIPTION_LABEL
from corp_orders.forms import LinkContractForm, QuoteForm
from corp_orders.models import FreightOrder, FreightOrdersSettings
from corp_orders.services.calculator import build_quote
from corp_orders.services.claim_tokens import make_claim_token, read_claim_token
from corp_orders.services.claims import can_claim_order, claim_order
from corp_orders.services.contracts import contract_creation_instructions, poll_order_contract
from corp_orders.services.lifecycle import can_cancel_order, cancel_order
from corp_orders.services.quote_session import load_quote, quote_fingerprint, store_quote
from corp_orders.services.systems import default_destination_system_name, search_solar_system_names
from corp_orders.tasks import notify_new_order_task, refresh_order_discord_task


def _main_character(request: HttpRequest):
    if not request.user.is_authenticated:
        return None
    try:
        return request.user.profile.main_character
    except Exception:
        return None


def _quote_inputs(form) -> dict:
    cleaned = form.cleaned_data
    return {
        "items_text": cleaned["items_text"],
        "speed": cleaned["speed"],
        "issuer_kind": cleaned["issuer_kind"],
        "final_destination_system": cleaned.get("final_destination_system") or "",
    }


@login_required
@permission_required("corp_orders.create_order", raise_exception=True)
@require_http_methods(["GET", "POST"])
def order_quote(request: HttpRequest) -> HttpResponse:
    config = FreightOrdersSettings.load()
    main = _main_character(request)
    if not main:
        messages.error(request, "Set a main character before creating orders.")
        return redirect("authentication:dashboard")

    quote = None
    if request.method == "POST":
        form = QuoteForm(request.POST)
        if form.is_valid():
            issuer = form.cleaned_data["issuer_kind"]
            if issuer == FreightOrder.IssuerKind.CORPORATION and not request.user.has_perm(
                "corp_orders.create_corp_contract"
            ):
                return HttpResponseForbidden("Corporation contracts require corp wallet permission.")

            inputs = _quote_inputs(form)
            fingerprint = quote_fingerprint(**inputs)
            action = request.POST.get("action")

            if action == "create":
                quote = load_quote(request, fingerprint=fingerprint)
            if quote is None:
                quote = build_quote(config=config, **inputs)
            if not quote.get("errors") and quote.get("lines"):
                store_quote(request, fingerprint=fingerprint, quote=quote)

            quote["form_cleaned"] = form.cleaned_data

            if action == "create" and not quote["errors"] and quote["lines"]:
                speed = form.cleaned_data["speed"]
                speed_label = SPEED_DESCRIPTION_LABEL[speed]
                total_volume = Decimal(str(quote["total_volume_m3"]))
                order = FreightOrder.objects.create(
                    created_by=request.user,
                    character_id=main.character_id,
                    character_name=main.character_name,
                    corporation_id=main.corporation_id,
                    corporation_name=getattr(main, "corporation_name", "") or "",
                    issuer_kind=issuer,
                    speed=speed,
                    status=FreightOrder.Status.PENDING_CONTRACT,
                    wallet_method=form.cleaned_data["wallet_method"],
                    wallet_notes=form.cleaned_data.get("wallet_notes") or "",
                    payback_on_completion=form.cleaned_data.get("payback_on_completion") or False,
                    final_destination_system=inputs["final_destination_system"],
                    items_text=form.cleaned_data["items_text"],
                    lines_json=quote["lines"],
                    total_volume_m3=total_volume,
                    items_subtotal_isk=quote["items_subtotal_isk"],
                    freight_isk=quote["freight_isk"],
                    speed_surcharge_isk=quote["speed_surcharge_isk"],
                    contract_price_isk=quote["contract_price_isk"],
                    pushx_normal_isk=quote.get("pushx_normal_isk"),
                    pushx_rush_isk=quote.get("pushx_rush_isk"),
                    freight_detail_json=quote.get("freight_detail") or {},
                    expiration_hours=quote["expiration_hours"],
                    contract_description=f"{speed_label} | pending",
                )
                order.contract_description = f"{speed_label} | {order.code}"
                order.save(update_fields=["contract_description"])
                notify_new_order_task.delay(order.pk)
                messages.success(request, f"Order {order.code} created — create the in-game contract next.")
                return redirect("corp_orders:order_detail", pk=order.pk)
    else:
        form = QuoteForm(
            initial={"final_destination_system": default_destination_system_name()}
        )

    return render(
        request,
        "corp_orders/quote.html",
        {
            "form": form,
            "quote": quote,
            "config": config,
            "title": "Corp stock order",
        },
    )


@login_required
@permission_required("corp_orders.claim_fulfillment", raise_exception=True)
@require_http_methods(["GET", "POST"])
def order_claim(request: HttpRequest, pk: int) -> HttpResponse:
    token = (request.GET.get("t") or request.POST.get("t") or "").strip()
    if read_claim_token(token) != pk:
        return HttpResponseForbidden("Invalid or expired claim link. Use the button on the latest Discord message.")

    order = get_object_or_404(FreightOrder, pk=pk)
    main = _main_character(request)
    if not main:
        messages.error(request, "Set a main character before claiming orders.")
        return redirect("authentication:dashboard")

    if order.claimed_by_id:
        messages.info(
            request,
            f"Already claimed by {order.claimed_character_name}.",
        )
        return redirect("corp_orders:order_detail", pk=order.pk)

    if not can_claim_order(order):
        messages.error(request, f"Order {order.code} cannot be claimed in its current state.")
        return redirect("corp_orders:order_detail", pk=order.pk)

    if request.method == "POST":
        if claim_order(
            order,
            user=request.user,
            character_id=main.character_id,
            character_name=main.character_name,
        ):
            refresh_order_discord_task.delay(order.pk)
            messages.success(
                request,
                f"You claimed filling for {order.code}. Discord has been updated.",
            )
            return redirect("corp_orders:order_detail", pk=order.pk)
        messages.error(request, "Could not claim this order (it may have just been claimed).")
        return redirect("corp_orders:order_detail", pk=order.pk)

    return render(
        request,
        "corp_orders/claim.html",
        {
            "order": order,
            "token": token,
            "title": f"Claim {order.code}",
        },
    )


@login_required
@permission_required("corp_orders.create_order", raise_exception=True)
def order_detail(request: HttpRequest, pk: int) -> HttpResponse:
    order = get_object_or_404(FreightOrder, pk=pk)
    if (
        order.created_by_id != request.user.id
        and not request.user.has_perm("corp_orders.manage_orders")
        and order.claimed_by_id != request.user.id
    ):
        return HttpResponseForbidden()

    config = FreightOrdersSettings.load()
    can_claim = (
        request.user.has_perm("corp_orders.claim_fulfillment")
        and can_claim_order(order)
    )
    can_manage = request.user.has_perm("corp_orders.manage_orders")

    if request.method == "POST" and request.POST.get("action") == "cancel":
        if not can_manage:
            return HttpResponseForbidden()
        if cancel_order(order):
            messages.success(request, f"Order {order.code} cancelled.")
        else:
            messages.error(request, f"Order {order.code} cannot be cancelled in its current state.")
        return redirect("corp_orders:order_detail", pk=order.pk)

    if request.method == "POST" and request.POST.get("action") == "poll":
        poll_order_contract(order)
        messages.info(request, "Contract status refreshed.")

    link_form = LinkContractForm()
    if request.method == "POST" and request.POST.get("action") == "link":
        link_form = LinkContractForm(request.POST)
        if link_form.is_valid():
            order.eve_contract_id = link_form.cleaned_data["eve_contract_id"]
            order.status = FreightOrder.Status.CONTRACT_LINKED
            order.save(update_fields=["eve_contract_id", "status", "updated_at"])
            poll_order_contract(order)
            messages.success(request, "Contract linked.")

    instructions = contract_creation_instructions(order, config=config)
    return render(
        request,
        "corp_orders/detail.html",
        {
            "order": order,
            "config": config,
            "instructions": instructions,
            "link_form": link_form,
            "can_cancel": can_manage and can_cancel_order(order),
            "can_claim": can_claim,
            "claim_token": make_claim_token(order.pk) if can_claim else "",
            "title": order.code,
        },
    )


@login_required
@permission_required("corp_orders.create_order", raise_exception=True)
@require_http_methods(["GET"])
def system_search(request: HttpRequest) -> JsonResponse:
    q = request.GET.get("q", "")
    try:
        limit = int(request.GET.get("limit", "25"))
    except ValueError:
        limit = 25
    try:
        systems = search_solar_system_names(q, limit=limit)
    except Exception:
        systems = []
    return JsonResponse({"systems": systems})


@login_required
@permission_required("corp_orders.create_order", raise_exception=True)
def order_list(request: HttpRequest) -> HttpResponse:
    qs = FreightOrder.objects.all()
    if not request.user.has_perm("corp_orders.manage_orders"):
        qs = qs.filter(created_by=request.user)
    return render(
        request,
        "corp_orders/list.html",
        {"orders": qs[:100], "title": "Corp stock orders"},
    )
