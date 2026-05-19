"""Recover Indy Hub migrations on PostgreSQL when DB state lags Django migration records."""

from __future__ import annotations

import os
import sys

MIGRATION_0023 = "0023_add_location_names_drop_facility_fields"
ORDER_REFERENCE_TABLES = (
    "indy_hub_materialexchangesellorder",
    "indy_hub_materialexchangebuyorder",
)


def _setup_django() -> None:
    os.environ.setdefault("DJANGO_SETTINGS_MODULE", "eve_auth.settings.local")
    site = os.environ.get("AA_SITE_ROOT", "/app/site")
    if site not in sys.path:
        sys.path.insert(0, site)
    import django

    django.setup()


def _column_exists(cursor, table: str, column: str) -> bool:
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


def _migration_applied(cursor, name: str) -> bool:
    cursor.execute(
        "SELECT 1 FROM django_migrations WHERE app = %s AND name = %s LIMIT 1",
        ["indy_hub", name],
    )
    return cursor.fetchone() is not None


def _record_migration(cursor, name: str) -> None:
    from django.utils import timezone

    cursor.execute(
        "INSERT INTO django_migrations (app, name, applied) VALUES (%s, %s, %s)",
        ["indy_hub", name, timezone.now()],
    )
    print(f"repair_indy_hub_migrations: recorded {name} as applied")


def repair_0023(cursor) -> None:
    if _migration_applied(cursor, MIGRATION_0023):
        return
    if not _column_exists(cursor, "indy_hub_indyblueprint", "location_name"):
        return
    _record_migration(cursor, MIGRATION_0023)


def repair_order_reference_columns(cursor) -> None:
    if not _migration_applied(cursor, "0049_add_order_reference"):
        return
    for table in ORDER_REFERENCE_TABLES:
        if _column_exists(cursor, table, "order_reference"):
            continue
        cursor.execute(
            f"ALTER TABLE {table} "
            "ADD COLUMN order_reference VARCHAR(50) DEFAULT '' NOT NULL"
        )
        print(f"repair_indy_hub_migrations: added order_reference on {table}")

    if not _migration_applied(cursor, "0050_populate_order_references"):
        return
    for table in ORDER_REFERENCE_TABLES:
        if not _column_exists(cursor, table, "order_reference"):
            continue
        cursor.execute(
            f"""
            UPDATE {table}
            SET order_reference = 'INDY-' || id::text
            WHERE order_reference = '' OR order_reference IS NULL
            """
        )
    print("repair_indy_hub_migrations: populated order_reference values")


def main() -> int:
    _setup_django()

    from django.db import connection

    if connection.vendor != "postgresql":
        return 0

    with connection.cursor() as cursor:
        repair_0023(cursor)
        repair_order_reference_columns(cursor)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
