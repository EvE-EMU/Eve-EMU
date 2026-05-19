from django.contrib.sessions.backends.db import SessionStore
from django.test import RequestFactory, TestCase, override_settings

from allianceauth import views

from .auth_utils import AuthUtils


@override_settings(ALLOWED_HOSTS=["example.com"])
class TestNightModeRedirectView(TestCase):
    @classmethod
    def setUpTestData(cls) -> None:
        cls.user = AuthUtils.create_user("my_user")
        cls.factory = RequestFactory()

    def _make_request(self, next_url=None):
        url = "/"
        if next_url:
            url = f"/?next={next_url}"
        request = self.factory.get(url)
        request.user = self.user
        request.session = SessionStore()
        return request

    def test_should_redirect_to_safe_url(self):
        request = self._make_request("/dashboard/")
        response = views.NightModeRedirectView.as_view()(request)
        self.assertEqual(response.status_code, 302)
        self.assertEqual(response.url, "/dashboard/")

    def test_should_block_redirect_to_external_url(self):
        request = self._make_request("https://evil.com")
        response = views.NightModeRedirectView.as_view()(request)
        self.assertEqual(response.status_code, 302)
        self.assertEqual(response.url, "/")

    def test_should_redirect_to_root_when_no_next(self):
        request = self._make_request()
        response = views.NightModeRedirectView.as_view()(request)
        self.assertEqual(response.status_code, 302)
        self.assertEqual(response.url, "/")


@override_settings(ALLOWED_HOSTS=["example.com"])
class TestThemeRedirectView(TestCase):
    @classmethod
    def setUpTestData(cls) -> None:
        cls.user = AuthUtils.create_user("theme_user")
        cls.factory = RequestFactory()

    def _make_request(self, next_url=None):
        url = "/"
        if next_url:
            url = f"/?next={next_url}"
        request = self.factory.post(url)
        request.user = self.user
        request.session = SessionStore()
        return request

    def test_should_redirect_to_safe_url(self):
        request = self._make_request("/dashboard/")
        response = views.ThemeRedirectView.as_view()(request)
        self.assertEqual(response.status_code, 302)
        self.assertEqual(response.url, "/dashboard/")

    def test_should_block_redirect_to_external_url(self):
        request = self._make_request("https://evil.com")
        response = views.ThemeRedirectView.as_view()(request)
        self.assertEqual(response.status_code, 302)
        self.assertEqual(response.url, "/")


@override_settings(ALLOWED_HOSTS=["example.com"])
class TestMinimizeSidebarRedirectView(TestCase):
    @classmethod
    def setUpTestData(cls) -> None:
        cls.user = AuthUtils.create_user("sidebar_user")
        cls.factory = RequestFactory()

    def _make_request(self, next_url=None):
        url = "/"
        if next_url:
            url = f"/?next={next_url}"
        request = self.factory.post(url)
        request.user = self.user
        request.session = SessionStore()
        return request

    def test_should_redirect_to_safe_url(self):
        request = self._make_request("/dashboard/")
        response = views.MinimizeSidebarRedirectView.as_view()(request)
        self.assertEqual(response.status_code, 302)
        self.assertEqual(response.url, "/dashboard/")

    def test_should_block_redirect_to_external_url(self):
        request = self._make_request("https://evil.com")
        response = views.MinimizeSidebarRedirectView.as_view()(request)
        self.assertEqual(response.status_code, 302)
        self.assertEqual(response.url, "/")


class TestCustomErrorHandlerViews(TestCase):
    @classmethod
    def setUpTestData(cls) -> None:
        cls.user = AuthUtils.create_user("my_user")
        cls.factory = RequestFactory()

    def test_should_return_status_code_400(self):
        # give
        request = self.factory.get("/")
        request.user = self.user
        # when
        response = views.Generic400Redirect(request)
        # then
        self.assertEqual(response.status_code, 400)

    def test_should_return_status_code_403(self):
        # give
        request = self.factory.get("/")
        request.user = self.user
        # when
        response = views.Generic403Redirect(request)
        # then
        self.assertEqual(response.status_code, 403)

    def test_should_return_status_code_404(self):
        # give
        request = self.factory.get("/")
        request.user = self.user
        # when
        response = views.Generic404Redirect(request)
        # then
        self.assertEqual(response.status_code, 404)

    def test_should_return_status_code_500(self):
        # give
        request = self.factory.get("/")
        request.user = self.user
        # when
        response = views.Generic500Redirect(request)
        # then
        self.assertEqual(response.status_code, 500)
