from django.test import SimpleTestCase

from standing_fleet_tracker.services.motd_text import normalize_fleet_text
from standing_fleet_tracker.services.standing_detect import text_matches_standing

WOMP_MOTD = (
    '<font size="14" color="#bfffffff"><br></font>'
    '<font size="14" color="#ff999999"><b>Welcome to WOMP Standing</b><br><br></font>'
    '<font size="12" color="#bfffffff">Staging:  </font>'
)


class StandingDetectTests(SimpleTestCase):
    def test_normalize_strips_html(self):
        self.assertIn("Welcome to WOMP Standing", normalize_fleet_text(WOMP_MOTD))

    def test_womp_motd_matches(self):
        self.assertTrue(text_matches_standing(WOMP_MOTD))
