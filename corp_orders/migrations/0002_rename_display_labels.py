from django.db import migrations


def _update_permission_labels(apps, schema_editor):
    Permission = apps.get_model("auth", "Permission")
    ContentType = apps.get_model("contenttypes", "ContentType")
    ct = ContentType.objects.filter(app_label="corp_orders", model="freightorder").first()
    if not ct:
        return
    labels = {
        "create_order": "Create corp stock orders",
        "create_corp_contract": "Create corp stock orders (corporation wallet)",
        "manage_orders": "Manage all corp stock orders",
    }
    for codename, name in labels.items():
        Permission.objects.filter(content_type=ct, codename=codename).update(name=name)


class Migration(migrations.Migration):

    dependencies = [
        ("corp_orders", "0001_initial"),
    ]

    operations = [
        migrations.AlterModelOptions(
            name="freightorderssettings",
            options={
                "verbose_name": "Corp stock order configuration",
                "verbose_name_plural": "Corp stock order configuration",
            },
        ),
        migrations.AlterModelOptions(
            name="freightorder",
            options={
                "ordering": ["-created_at"],
                "verbose_name": "Corp stock order",
                "verbose_name_plural": "Corp stock orders",
                "permissions": [
                    ("create_order", "Create corp stock orders"),
                    ("create_corp_contract", "Create corp stock orders (corporation wallet)"),
                    ("manage_orders", "Manage all corp stock orders"),
                ],
            },
        ),
        migrations.RunPython(_update_permission_labels, migrations.RunPython.noop),
    ]
