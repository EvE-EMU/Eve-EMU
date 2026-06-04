from __future__ import annotations

import os

from emu_moons.access import nav_context
from emu_moons.models import EmuMoonsSettings


def emu_moons_nav(request):
    ctx = nav_context(request)
    cfg = EmuMoonsSettings.load()
    ctx["emu_moons_tax_corp_name"] = cfg.tax_corp_name
    ctx["emu_moons_ad_contact"] = (
        os.environ.get("AA_EMU_MOONS_AD_CONTACT", "Sevey").strip() or "Sevey"
    )
    ctx["emu_moons_ad_image_1"] = os.environ.get("AA_EMU_MOONS_AD_IMAGE_1", "").strip()
    ctx["emu_moons_ad_image_2"] = os.environ.get("AA_EMU_MOONS_AD_IMAGE_2", "").strip()
    return ctx
