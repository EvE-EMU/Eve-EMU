# Django
# Alliance Auth
from allianceauth import urls
from django.urls import include, re_path

urlpatterns = [
    # Alliance Auth URLs
    re_path(r"", include(urls)),
]
