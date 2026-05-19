from django.test import TestCase

from mailrelay.core.xml_converter import eve_xml_to_discord_markup


class TestXmlToMarkup(TestCase):
    def test_should_replace_line_breaks(self):
        # when
        result = eve_xml_to_discord_markup("alpha<br>bravo<br><br>charlie")
        # then
        self.assertEqual(result, "alpha\nbravo\n\ncharlie")

    def test_should_convert_bold(self):
        # when
        result = eve_xml_to_discord_markup("<b>alpha</b>")
        # then
        self.assertEqual(result, "**alpha**")

    def test_should_convert_italic(self):
        # when
        result = eve_xml_to_discord_markup("<i>alpha</i>")
        # then
        self.assertEqual(result, "_alpha_")

    def test_should_convert_underline(self):
        # when
        result = eve_xml_to_discord_markup("<u>alpha</u>")
        # then
        self.assertEqual(result, "__alpha__")

    def test_should_convert_url_links(self):
        # when
        result = eve_xml_to_discord_markup(
            '<a href="https://www.example.com">alpha</a>'
        )
        # then
        self.assertEqual(result, "[alpha](https://www.example.com)")

    def test_should_handle_other_links(self):
        # when
        result = eve_xml_to_discord_markup(
            '<a href="showinfo:35825//1033237775571">alpha</a>'
        )
        # then
        self.assertEqual(result, "**alpha**")
