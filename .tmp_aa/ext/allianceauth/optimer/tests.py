from django.test import TestCase

from allianceauth.optimer.form_widgets import DataListWidget


class TestDataListWidget(TestCase):
    def test_should_render_options(self):
        widget = DataListWidget(data_list=["Fleet", "Mining"], name="ops")
        html = widget.render("type", "")
        self.assertIn('<option value="Fleet">', html)
        self.assertIn('<option value="Mining">', html)
        self.assertIn('<datalist id="list__ops">', html)

    def test_should_escape_html_in_options(self):
        malicious = '"><script>alert(1)</script>'
        widget = DataListWidget(data_list=[malicious], name="ops")
        html = widget.render("type", "")
        self.assertNotIn("<script>", html)
        self.assertNotIn(malicious, html)
        self.assertIn("&lt;script&gt;", html)

    def test_should_handle_empty_list(self):
        widget = DataListWidget(data_list=[], name="ops")
        html = widget.render("type", "")
        self.assertIn('<datalist id="list__ops">', html)
        self.assertNotIn("<option", html)
