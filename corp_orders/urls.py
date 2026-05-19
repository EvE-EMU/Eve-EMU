from django.urls import path

from corp_orders import views

app_name = "corp_orders"

urlpatterns = [
    path("", views.order_list, name="order_list"),
    path("new/", views.order_quote, name="order_quote"),
    path("api/systems/", views.system_search, name="system_search"),
    path("<int:pk>/", views.order_detail, name="order_detail"),
]
