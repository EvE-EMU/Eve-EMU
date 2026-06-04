"""Point tax wallet at Guns-R-Us (98633922) and configure mail sender."""

from django.db import migrations

GUNS_R_US_CORP_ID = 98633922
EL_EMU_MOON_TZAR_CHAR_ID = 2124416360
EL_EMU_MOON_TZAR_TOKEN_ID = 1016


def fix_settings(apps, schema_editor):
    EmuMoonsSettings = apps.get_model("emu_moons", "EmuMoonsSettings")
    EmuMoonsSettings.objects.update_or_create(
        pk=1,
        defaults={
            "corporation_id": GUNS_R_US_CORP_ID,
            "esi_token_id": EL_EMU_MOON_TZAR_TOKEN_ID,
            "mail_sender_character_id": EL_EMU_MOON_TZAR_CHAR_ID,
        },
    )


class Migration(migrations.Migration):
    dependencies = [
        ("emu_moons", "0005_invoice_per_character"),
    ]

    operations = [
        migrations.RunPython(fix_settings, migrations.RunPython.noop),
    ]
