from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [
        ("moonrentals", "0001_initial"),
    ]

    operations = [
        migrations.AddField(
            model_name="rentalmodulesettings",
            name="auto_approve_applications",
            field=models.BooleanField(
                default=False,
                help_text="Instantly create a lease when a renter submits an application.",
            ),
        ),
        migrations.AddField(
            model_name="rentalmodulesettings",
            name="fuel_reference_hours",
            field=models.PositiveIntegerField(
                default=720,
                help_text="Hours of fuel at 100%% when deriving %% from aa-structures expiry.",
            ),
        ),
    ]
