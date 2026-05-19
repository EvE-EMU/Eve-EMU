from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("corp_orders", "0002_rename_display_labels"),
    ]

    operations = [
        migrations.AddField(
            model_name="freightorder",
            name="final_destination_system",
            field=models.CharField(
                blank=True,
                default="",
                help_text="Officer-entered final delivery system (freight is quoted to the hub only).",
                max_length=64,
            ),
        ),
    ]
