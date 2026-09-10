from __future__ import annotations

from django.db import migrations, models


class Migration(migrations.Migration):

    initial = True

    dependencies = []

    operations = [
        migrations.CreateModel(
            name="PenguinFitting",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("owner_user_id", models.BigIntegerField(db_index=True)),
                ("owner_name", models.CharField(blank=True, default="", max_length=100)),
                ("name", models.CharField(max_length=120)),
                ("ship_type_id", models.IntegerField(default=0)),
                ("eft", models.TextField()),
                (
                    "scope",
                    models.CharField(
                        choices=[("private", "Private"), ("corp", "Corp"), ("alliance", "Alliance")],
                        db_index=True,
                        default="private",
                        max_length=10,
                    ),
                ),
                ("corp_id", models.BigIntegerField(db_index=True, default=0)),
                ("alliance_id", models.BigIntegerField(db_index=True, default=0)),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("updated_at", models.DateTimeField(auto_now=True)),
            ],
            options={
                "ordering": ["name", "id"],
            },
        ),
    ]
