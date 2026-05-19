# Patched for PostgreSQL: add order_reference columns (eve-emu Docker).
from django.db import migrations, models


def _pg_column_exists(cursor, table: str, column: str) -> bool:
    cursor.execute(
        """
        SELECT 1
        FROM information_schema.columns
        WHERE table_schema = current_schema()
          AND table_name = %s
          AND column_name = %s
        LIMIT 1
        """,
        [table, column],
    )
    return cursor.fetchone() is not None


def add_order_reference_columns(apps, schema_editor):
    from django.db import connection

    vendor = connection.vendor

    with connection.cursor() as cursor:
        if vendor == "mysql":
            cursor.execute(
                """
                SELECT COLUMN_NAME FROM INFORMATION_SCHEMA.COLUMNS
                WHERE TABLE_NAME = 'indy_hub_materialexchangesellorder'
                AND TABLE_SCHEMA = DATABASE()
                AND COLUMN_NAME = 'order_reference'
            """
            )
            if not cursor.fetchone():
                cursor.execute(
                    """
                    ALTER TABLE indy_hub_materialexchangesellorder
                    ADD COLUMN order_reference VARCHAR(50) DEFAULT '' NOT NULL
                """
                )

            cursor.execute(
                """
                SELECT COLUMN_NAME FROM INFORMATION_SCHEMA.COLUMNS
                WHERE TABLE_NAME = 'indy_hub_materialexchangebuyorder'
                AND TABLE_SCHEMA = DATABASE()
                AND COLUMN_NAME = 'order_reference'
            """
            )
            if not cursor.fetchone():
                cursor.execute(
                    """
                    ALTER TABLE indy_hub_materialexchangebuyorder
                    ADD COLUMN order_reference VARCHAR(50) DEFAULT '' NOT NULL
                """
                )
        elif vendor == "postgresql":
            for table in (
                "indy_hub_materialexchangesellorder",
                "indy_hub_materialexchangebuyorder",
            ):
                if not _pg_column_exists(cursor, table, "order_reference"):
                    cursor.execute(
                        f"ALTER TABLE {table} "
                        "ADD COLUMN order_reference VARCHAR(50) DEFAULT '' NOT NULL"
                    )
        elif vendor == "sqlite":
            cursor.execute("PRAGMA table_info(indy_hub_materialexchangesellorder)")
            columns = [row[1] for row in cursor.fetchall()]
            if "order_reference" not in columns:
                cursor.execute(
                    """
                    ALTER TABLE indy_hub_materialexchangesellorder
                    ADD COLUMN order_reference VARCHAR(50) DEFAULT ''
                """
                )

            cursor.execute("PRAGMA table_info(indy_hub_materialexchangebuyorder)")
            columns = [row[1] for row in cursor.fetchall()]
            if "order_reference" not in columns:
                cursor.execute(
                    """
                    ALTER TABLE indy_hub_materialexchangebuyorder
                    ADD COLUMN order_reference VARCHAR(50) DEFAULT ''
                """
                )


def reverse_add_order_reference_columns(apps, schema_editor):
    pass


class Migration(migrations.Migration):
    dependencies = [
        ("indy_hub", "0048_remove_market_group_filters"),
    ]

    operations = [
        migrations.RunPython(
            add_order_reference_columns,
            reverse_add_order_reference_columns,
        ),
        migrations.SeparateDatabaseAndState(
            state_operations=[
                migrations.AddField(
                    model_name="materialexchangesellorder",
                    name="order_reference",
                    field=models.CharField(
                        blank=True,
                        db_index=True,
                        help_text="Unique order reference (INDY-{id}) for contract matching",
                        max_length=50,
                        default="",
                    ),
                ),
                migrations.AddField(
                    model_name="materialexchangebuyorder",
                    name="order_reference",
                    field=models.CharField(
                        blank=True,
                        db_index=True,
                        help_text="Unique order reference (INDY-{id}) for contract matching",
                        max_length=50,
                        default="",
                    ),
                ),
            ],
            database_operations=[],
        ),
    ]
