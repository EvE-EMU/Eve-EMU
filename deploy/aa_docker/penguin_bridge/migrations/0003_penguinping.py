from __future__ import annotations

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("penguin_bridge", "0002_penguinwhmap"),
    ]

    operations = [
        migrations.CreateModel(
            name="PenguinPing",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("scope", models.CharField(choices=[("corp", "Corp"), ("alliance", "Alliance")], db_index=True, max_length=10)),
                ("key", models.BigIntegerField(db_index=True)),
                ("kind", models.CharField(default="misc", max_length=16)),
                ("text", models.TextField()),
                ("system", models.CharField(blank=True, default="", max_length=64)),
                ("at_unix", models.BigIntegerField(default=0)),
                ("author", models.CharField(blank=True, default="", max_length=100)),
                ("created_at", models.DateTimeField(auto_now_add=True, db_index=True)),
                ("expires_at", models.DateTimeField(db_index=True)),
            ],
            options={
                "ordering": ["-created_at", "-id"],
            },
        ),
    ]
