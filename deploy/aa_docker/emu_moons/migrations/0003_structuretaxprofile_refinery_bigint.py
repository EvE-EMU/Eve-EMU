from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [
        ("emu_moons", "0002_structuretaxprofile_private_owner"),
    ]

    operations = [
        migrations.AlterField(
            model_name="structuretaxprofile",
            name="moonmining_refinery_id",
            field=models.BigIntegerField(
                blank=True, db_index=True, null=True, unique=True
            ),
        ),
    ]
