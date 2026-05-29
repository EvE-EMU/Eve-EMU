from types import SimpleNamespace

from django.http import HttpResponse
from django.test import RequestFactory

from .. import auth_hooks
from ..decorators import (
    fetch_character_if_allowed,
    fetch_token_for_character,
    fetch_user_if_allowed,
)
from ..forms import SettingsForm
from ..models import Settings
from ..templatetags.settings import analytics
from .base import MiningTaxesBaseTestCase


class TestMisc(MiningTaxesBaseTestCase):
    def setUp(self):
        super().setUp()
        self.factory = RequestFactory()

    def test_fetch_user_if_allowed(self):
        @fetch_user_if_allowed()
        def view(request, user_pk, user):
            return HttpResponse(str(user.pk))

        request = self.factory.get("/")
        request.user = self.user
        self.assertEqual(view(request, self.user.pk).status_code, 200)
        self.assertEqual(view(request, 9999).status_code, 404)

    def test_fetch_character_if_allowed(self):
        @fetch_character_if_allowed()
        def view(request, character_pk, character):
            return HttpResponse(str(character.pk))

        request = self.factory.get("/")
        request.user = self.user
        self.assertEqual(view(request, self.main_character.pk).status_code, 200)
        request.user = self.other_user
        self.assertEqual(view(request, self.main_character.pk).status_code, 403)
        request.user = self.user
        self.assertEqual(view(request, 9999).status_code, 404)

    def test_fetch_token_for_character(self):
        class Dummy:
            def fetch_token(self, scopes=None):
                return SimpleNamespace(character_name="Dummy", pk=1)

        @fetch_token_for_character("scope")
        def method(character, token):
            return token

        self.assertEqual(method(Dummy()).character_name, "Dummy")

    def test_settings_form_and_model(self):
        settings = Settings.load()
        form = SettingsForm(instance=settings)
        self.assertIn("phrase", form.fields)
        settings.phrase = "abc"
        settings.save()
        self.assertEqual(Settings.load().phrase, "abc")
        settings.delete()
        self.assertEqual(Settings.load().phrase, "abc")

    def test_auth_hooks(self):
        menu = auth_hooks.register_menu()
        request = self.factory.get("/")
        request.user = self.user
        self.assertTrue(menu.render(request))
        request.user = self.other_user
        self.assertTrue(menu.render(request))
        self.assertTrue(auth_hooks.register_urls())

    def test_analytics_tag(self):
        self.assertTrue(analytics())
