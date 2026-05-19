"""Converters for XML."""

import unicodedata

from bs4 import BeautifulSoup

from eveuniverse.core import evexml

from allianceauth.services.hooks import get_extension_logger
from app_utils.logging import LoggerAddTag

from mailrelay import __title__

logger = LoggerAddTag(get_extension_logger(__name__), __title__)


def eve_xml_to_discord_markup(xml_doc: str) -> str:
    """Converts Eve Online xml to Discord markup."""
    xml_doc = unicodedata.normalize("NFKC", xml_doc)
    xml_doc = evexml.remove_loc_tag(xml_doc)
    soup = BeautifulSoup(xml_doc, "html.parser")
    for element in soup.find_all("br"):
        element.replace_with("\n")
    for element in soup.find_all("b"):
        element.replace_with(f"**{element.string}**")
    for element in soup.find_all("i"):
        element.replace_with(f"_{element.string}_")
    for element in soup.find_all("u"):
        element.replace_with(f"__{element.string}__")
    for element in soup.find_all("a"):
        text = element.string
        url = evexml.eve_link_to_url(element["href"])
        if url:
            element.replace_with(f"[{text}]({url})")
        else:
            element.replace_with(f"**{text}**")
    markup_text = soup.get_text()
    logger.debug("Markdown text:\n%s", markup_text)
    return markup_text
