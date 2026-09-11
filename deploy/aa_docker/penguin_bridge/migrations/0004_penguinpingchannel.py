from __future__ import annotations

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("penguin_bridge", "0003_penguinping"),
    ]

    operations = [
        migrations.CreateModel(
            name="PenguinPingChannel",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("discord_channel_id", models.BigIntegerField(db_index=True, unique=True)),
                ("label", models.CharField(blank=True, default="", max_length=40)),
                ("scope", models.CharField(default="alliance", max_length=10)),
                ("key", models.BigIntegerField()),
                ("kind", models.CharField(default="misc", max_length=16)),
                ("ttl_hours", models.PositiveIntegerField(default=6)),
                ("enabled", models.BooleanField(default=True)),
            ],
        ),
    ]
