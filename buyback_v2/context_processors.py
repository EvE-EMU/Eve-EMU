def buyback_pricing_tier(request):
    return {"pricing_ctx": getattr(request, "buyback_pricing_ctx", None)}
