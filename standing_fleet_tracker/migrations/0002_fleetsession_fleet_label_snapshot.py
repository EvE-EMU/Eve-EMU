from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("standing_fleet_tracker", "0001_initial"),
    ]

    operations = [
        migrations.AddField(
            model_name="fleetsession",
            name="fleet_label_snapshot",
            field=models.CharField(
                blank=True,
                default="",
                help_text="Fleet advert / AFAT name when MOTD is unavailable to members.",
                max_length=255,
            ),
        ),
    ]
