from django.db import migrations


class Migration(migrations.Migration):

    dependencies = [
        ("emu_moons", "0004_tax_effective_date"),
    ]

    operations = [
        migrations.AlterUniqueTogether(
            name="emuinvoice",
            unique_together={("extraction", "character_id")},
        ),
    ]
