from django.urls import path

from . import views

app_name = "marketmanager"

urlpatterns = [
    path('', views.marketbrowser, name="index"),
    path('marketbrowser', views.marketbrowser, name="marketbrowser"),
    path('marketmanager', views.marketbrowser, name="marketmanager"),
    path('marketwatches', views.marketwatches, name="marketwatches"),
    path(
        'marketbrowser/ajax/search',
        views.marketbrowser_autocomplete,
        name="marketbrowser_autocomplete"
    ),
    path(
        'marketbrowser/ajax/buy_orders',
        views.marketbrowser_buy_orders,
        name="marketbrowser_buy_orders"
    ),
    path(
        'marketbrowser/ajax/sell_orders',
        views.marketbrowser_sell_orders,
        name="marketbrowser_sell_orders"
    ),
    path('char/add', views.add_char, name="add_char"),
    path('corp/add', views.add_corp, name="add_corp")
]
