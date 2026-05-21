from django.apps import AppConfig


class MarketBridgeConfig(AppConfig):
    default_auto_field = "django.db.models.BigAutoField"
    name = "market_bridge"
    label = "market_bridge"

    def ready(self) -> None:
        from django.urls import path

        import eve_auth.urls as root_urls

        from market_bridge.views import access_token_view

        route = path("internal/market/access-token", access_token_view, name="market_access_token")
        if not any(
            getattr(p, "name", None) == "market_access_token"
            for p in root_urls.urlpatterns
        ):
            root_urls.urlpatterns.insert(0, route)
