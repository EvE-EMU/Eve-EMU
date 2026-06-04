from datetime import date

from django.db import migrations, models


def set_default_cutoff(apps, schema_editor):
    EmuMoonsSettings = apps.get_model("emu_moons", "EmuMoonsSettings")
    EmuMoonsSettings.objects.update_or_create(
        pk=1,
        defaults={"tax_effective_date": date(2026, 6, 1)},
    )


class Migration(migrations.Migration):

    dependencies = [
        ("emu_moons", "0003_structuretaxprofile_refinery_bigint"),
    ]

    operations = [
        migrations.AddField(
            model_name="emumoonssettings",
            name="tax_effective_date",
            field=models.DateField(
                default=date(2026, 6, 1),
                help_text="No tax invoices, penalties, or naughty-list entries before this date (inclusive).",
            ),
        ),
        migrations.RunPython(set_default_cutoff, migrations.RunPython.noop),
    ]
