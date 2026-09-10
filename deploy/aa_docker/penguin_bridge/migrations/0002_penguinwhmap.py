from __future__ import annotations

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("penguin_bridge", "0001_initial"),
    ]

    operations = [
        migrations.CreateModel(
            name="PenguinWhMap",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("scope", models.CharField(db_index=True, default="personal", max_length=10)),
                ("key", models.BigIntegerField(db_index=True, default=0)),
                ("data", models.JSONField(default=dict)),
                ("rev", models.BigIntegerField(default=0)),
                ("updated_by", models.CharField(blank=True, default="", max_length=100)),
                ("updated_at", models.DateTimeField(auto_now=True)),
            ],
            options={
                "unique_together": {("scope", "key")},
            },
        ),
    ]
