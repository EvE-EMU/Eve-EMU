# Patched for PostgreSQL: populate order_reference values (eve-emu Docker).
from django.db import migrations


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


def populate_order_references(apps, schema_editor):
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

            cursor.execute(
                """
                UPDATE indy_hub_materialexchangesellorder
                SET order_reference = CONCAT('INDY-', id)
                WHERE order_reference = '' OR order_reference IS NULL
            """
            )

            cursor.execute(
                """
                UPDATE indy_hub_materialexchangebuyorder
                SET order_reference = CONCAT('INDY-', id)
                WHERE order_reference = '' OR order_reference IS NULL
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
            cursor.execute(
                """
                UPDATE indy_hub_materialexchangesellorder
                SET order_reference = 'INDY-' || id::text
                WHERE order_reference = '' OR order_reference IS NULL
                """
            )
            cursor.execute(
                """
                UPDATE indy_hub_materialexchangebuyorder
                SET order_reference = 'INDY-' || id::text
                WHERE order_reference = '' OR order_reference IS NULL
                """
            )
        elif vendor == "sqlite":
            cursor.execute(
                """
                UPDATE indy_hub_materialexchangesellorder
                SET order_reference = 'INDY-' || id
                WHERE order_reference = '' OR order_reference IS NULL
            """
            )

            cursor.execute(
                """
                UPDATE indy_hub_materialexchangebuyorder
                SET order_reference = 'INDY-' || id
                WHERE order_reference = '' OR order_reference IS NULL
            """
            )


def reverse_populate_order_references(apps, schema_editor):
    pass


class Migration(migrations.Migration):
    dependencies = [
        ("indy_hub", "0049_add_order_reference"),
    ]

    operations = [
        migrations.RunPython(
            populate_order_references,
            reverse_populate_order_references,
        ),
    ]
