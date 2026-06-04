from django.conf import settings
from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):
    dependencies = [
        ("emu_moons", "0001_initial"),
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
    ]

    operations = [
        migrations.AddField(
            model_name="structuretaxprofile",
            name="private_owner",
            field=models.ForeignKey(
                blank=True,
                help_text="Member who can see this private moon on the extraction calendar",
                null=True,
                on_delete=django.db.models.deletion.SET_NULL,
                related_name="emu_moons_private_structures",
                to=settings.AUTH_USER_MODEL,
            ),
        ),
    ]
