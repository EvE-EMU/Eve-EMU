#!/usr/bin/env python3
"""Apply Alembic migrations; stamp head when schema already exists from create_all."""

from __future__ import annotations

import subprocess
import sys

from sqlalchemy import text
from sqlalchemy.ext.asyncio import create_async_engine

from app.config import settings


_INTEL_TAGS_DDL = [
    """
    CREATE TABLE IF NOT EXISTS emums_intel_entity_tags (
        id INT NOT NULL AUTO_INCREMENT PRIMARY KEY,
        owner_user_id INT NOT NULL,
        entity_id BIGINT NOT NULL,
        entity_kind VARCHAR(16) NOT NULL DEFAULT 'character',
        entity_name VARCHAR(256) NOT NULL DEFAULT '',
        tag_type VARCHAR(32) NOT NULL,
        linked_character_id BIGINT NULL,
        linked_character_name VARCHAR(128) NOT NULL DEFAULT '',
        notes TEXT NOT NULL,
        created_by_character_id BIGINT NOT NULL DEFAULT 0,
        created_by_character_name VARCHAR(128) NOT NULL DEFAULT '',
        active TINYINT(1) NOT NULL DEFAULT 1,
        created_at DATETIME(6) NOT NULL DEFAULT CURRENT_TIMESTAMP(6),
        updated_at DATETIME(6) NOT NULL DEFAULT CURRENT_TIMESTAMP(6)
            ON UPDATE CURRENT_TIMESTAMP(6),
        UNIQUE KEY uq_intel_tag_owner_entity_type (owner_user_id, entity_id, tag_type),
        INDEX ix_intel_tags_owner (owner_user_id),
        INDEX ix_intel_tags_entity (entity_id),
        INDEX ix_intel_tags_type (tag_type),
        INDEX ix_intel_tags_linked (linked_character_id),
        INDEX ix_intel_tags_active (active)
    )
    """,
]


_ONBOARDING_TABLES_DDL = [
    """
    CREATE TABLE IF NOT EXISTS emums_onboarding_tasks (
        id INT NOT NULL AUTO_INCREMENT PRIMARY KEY,
        slug VARCHAR(64) NOT NULL,
        title VARCHAR(128) NOT NULL,
        description TEXT NOT NULL,
        category VARCHAR(32) NOT NULL DEFAULT 'setup',
        points INT NOT NULL DEFAULT 10,
        sort_order INT NOT NULL DEFAULT 0,
        window_id VARCHAR(64) NOT NULL DEFAULT '',
        auto_check VARCHAR(64) NOT NULL DEFAULT '',
        active TINYINT(1) NOT NULL DEFAULT 1,
        UNIQUE KEY uq_onboarding_tasks_slug (slug)
    )
    """,
    """
    CREATE TABLE IF NOT EXISTS emums_onboarding_progress (
        id INT NOT NULL AUTO_INCREMENT PRIMARY KEY,
        character_id BIGINT NOT NULL,
        character_name VARCHAR(128) NOT NULL DEFAULT '',
        task_id INT NOT NULL,
        completed TINYINT(1) NOT NULL DEFAULT 0,
        completed_at DATETIME(6) NULL,
        notes VARCHAR(256) NOT NULL DEFAULT '',
        UNIQUE KEY uq_onboarding_char_task (character_id, task_id),
        INDEX ix_onboarding_progress_character_id (character_id),
        INDEX ix_onboarding_progress_task_id (task_id)
    )
    """,
    """
    CREATE TABLE IF NOT EXISTS emums_admission_kpis (
        id INT NOT NULL AUTO_INCREMENT PRIMARY KEY,
        slug VARCHAR(64) NOT NULL,
        label VARCHAR(128) NOT NULL,
        description TEXT NOT NULL,
        weight DOUBLE NOT NULL DEFAULT 1,
        metric_key VARCHAR(64) NOT NULL,
        min_value DOUBLE NOT NULL DEFAULT 0,
        target_value DOUBLE NOT NULL DEFAULT 100,
        active TINYINT(1) NOT NULL DEFAULT 1,
        sort_order INT NOT NULL DEFAULT 0,
        UNIQUE KEY uq_admission_kpis_slug (slug)
    )
    """,
    """
    CREATE TABLE IF NOT EXISTS emums_admission_config (
        id INT NOT NULL AUTO_INCREMENT PRIMARY KEY,
        admit_threshold DOUBLE NOT NULL DEFAULT 60,
        review_threshold DOUBLE NOT NULL DEFAULT 40,
        updated_at DATETIME(6) NOT NULL DEFAULT CURRENT_TIMESTAMP(6)
            ON UPDATE CURRENT_TIMESTAMP(6)
    )
    """,
    """
    CREATE TABLE IF NOT EXISTS emums_character_standings (
        id INT NOT NULL AUTO_INCREMENT PRIMARY KEY,
        character_id BIGINT NOT NULL,
        from_id BIGINT NOT NULL,
        from_type VARCHAR(16) NOT NULL DEFAULT 'character',
        from_name VARCHAR(128) NOT NULL DEFAULT '',
        standing DOUBLE NOT NULL DEFAULT 0,
        synced_at DATETIME(6) NOT NULL DEFAULT CURRENT_TIMESTAMP(6)
            ON UPDATE CURRENT_TIMESTAMP(6),
        UNIQUE KEY uq_char_standing (character_id, from_id, from_type),
        INDEX ix_character_standings_character_id (character_id),
        INDEX ix_character_standings_from_id (from_id)
    )
    """,
]


_STOREFRONT_TABLES_DDL = [
    """
    CREATE TABLE IF NOT EXISTS emums_storefront_config (
        id INT NOT NULL AUTO_INCREMENT PRIMARY KEY,
        enabled TINYINT(1) NOT NULL DEFAULT 1,
        corp_name VARCHAR(128) NOT NULL DEFAULT 'Solar Extraction Venture',
        corp_id BIGINT NOT NULL DEFAULT 0,
        inventory_character_ids VARCHAR(512) NOT NULL DEFAULT '',
        corp_hangar_flag VARCHAR(32) NOT NULL DEFAULT 'CorpSAG1',
        structure_id BIGINT NOT NULL DEFAULT 0,
        structure_name_contains VARCHAR(128) NOT NULL DEFAULT '',
        system_name_contains VARCHAR(64) NOT NULL DEFAULT '',
        price_hub VARCHAR(32) NOT NULL DEFAULT 'jita',
        discord_webhook_url VARCHAR(512) NOT NULL DEFAULT '',
        staff_notify_character_id BIGINT NOT NULL DEFAULT 0,
        contract_expiration_hours INT NOT NULL DEFAULT 24,
        updated_at DATETIME(6) NOT NULL DEFAULT CURRENT_TIMESTAMP(6) ON UPDATE CURRENT_TIMESTAMP(6)
    )
    """,
    """
    CREATE TABLE IF NOT EXISTS emums_storefront_pickup_locations (
        id INT NOT NULL AUTO_INCREMENT PRIMARY KEY,
        label VARCHAR(128) NOT NULL,
        structure_name VARCHAR(256) NOT NULL DEFAULT '',
        structure_id BIGINT NOT NULL DEFAULT 0,
        system_name VARCHAR(64) NOT NULL DEFAULT '',
        location_hint VARCHAR(512) NOT NULL DEFAULT '',
        is_default TINYINT(1) NOT NULL DEFAULT 0,
        active TINYINT(1) NOT NULL DEFAULT 1,
        sort_order INT NOT NULL DEFAULT 0
    )
    """,
    """
    CREATE TABLE IF NOT EXISTS emums_storefront_item_overrides (
        id INT NOT NULL AUTO_INCREMENT PRIMARY KEY,
        type_id INT NOT NULL,
        type_name VARCHAR(256) NOT NULL DEFAULT '',
        price_override_isk DECIMAL(16,2) NULL,
        fake_qty_add INT NOT NULL DEFAULT 0,
        hidden TINYINT(1) NOT NULL DEFAULT 0,
        note VARCHAR(512) NOT NULL DEFAULT '',
        UNIQUE KEY uq_storefront_override_type (type_id),
        INDEX ix_storefront_override_type_id (type_id)
    )
    """,
    """
    CREATE TABLE IF NOT EXISTS emums_storefront_kits (
        id INT NOT NULL AUTO_INCREMENT PRIMARY KEY,
        name VARCHAR(256) NOT NULL,
        description TEXT NOT NULL,
        price_isk DECIMAL(16,2) NULL,
        active TINYINT(1) NOT NULL DEFAULT 1,
        sort_order INT NOT NULL DEFAULT 0
    )
    """,
    """
    CREATE TABLE IF NOT EXISTS emums_storefront_kit_items (
        id INT NOT NULL AUTO_INCREMENT PRIMARY KEY,
        kit_id INT NOT NULL,
        type_id INT NOT NULL,
        type_name VARCHAR(256) NOT NULL DEFAULT '',
        quantity INT NOT NULL DEFAULT 1,
        INDEX ix_storefront_kit_items_kit_id (kit_id),
        INDEX ix_storefront_kit_items_type_id (type_id),
        CONSTRAINT fk_storefront_kit_items_kit
            FOREIGN KEY (kit_id) REFERENCES emums_storefront_kits(id) ON DELETE CASCADE
    )
    """,
    """
    CREATE TABLE IF NOT EXISTS emums_storefront_orders (
        id INT NOT NULL AUTO_INCREMENT PRIMARY KEY,
        order_code VARCHAR(32) NOT NULL,
        buyer_character_id BIGINT NOT NULL DEFAULT 0,
        buyer_character_name VARCHAR(128) NOT NULL,
        pickup_location_id INT NULL,
        pickup_label VARCHAR(128) NOT NULL DEFAULT '',
        lines_json TEXT NOT NULL,
        total_isk DECIMAL(20,2) NOT NULL DEFAULT 0,
        contract_description VARCHAR(256) NOT NULL DEFAULT '',
        status VARCHAR(24) NOT NULL DEFAULT 'pending',
        mail_sent_buyer TINYINT(1) NOT NULL DEFAULT 0,
        mail_sent_corp TINYINT(1) NOT NULL DEFAULT 0,
        discord_sent TINYINT(1) NOT NULL DEFAULT 0,
        webhook_sent TINYINT(1) NOT NULL DEFAULT 0,
        mail_error VARCHAR(2000) NOT NULL DEFAULT '',
        notes TEXT NOT NULL,
        created_at DATETIME(6) NOT NULL DEFAULT CURRENT_TIMESTAMP(6),
        UNIQUE KEY uq_storefront_order_code (order_code),
        INDEX ix_storefront_orders_buyer (buyer_character_id),
        INDEX ix_storefront_orders_status (status),
        INDEX ix_storefront_orders_created (created_at)
    )
    """,
]


async def _needs_stamp() -> bool:
    engine = create_async_engine(settings.database_url)
    try:
        async with engine.connect() as conn:
            try:
                row = await conn.execute(text("SELECT version_num FROM alembic_version LIMIT 1"))
                if row.scalar():
                    return False
            except Exception:
                pass
            row = await conn.execute(text("SHOW TABLES LIKE 'emums_org_settings'"))
            return row.first() is not None
    finally:
        await engine.dispose()


async def _ensure_schema_extras() -> None:
    """Idempotent DDL for audit extras when Alembic revision files are unavailable."""
    engine = create_async_engine(settings.database_url)
    try:
        async with engine.begin() as conn:
            await conn.execute(
                text(
                    """
                    CREATE TABLE IF NOT EXISTS emums_universe_locations (
                        entity_id BIGINT NOT NULL PRIMARY KEY,
                        name VARCHAR(256) NOT NULL DEFAULT '',
                        entity_type VARCHAR(32) NOT NULL DEFAULT '',
                        solar_system_id INT NULL,
                        updated_at DATETIME(6) NOT NULL DEFAULT CURRENT_TIMESTAMP(6)
                            ON UPDATE CURRENT_TIMESTAMP(6),
                        INDEX ix_emums_universe_locations_solar_system_id (solar_system_id)
                    )
                    """
                )
            )
            col = await conn.execute(
                text(
                    """
                    SELECT COUNT(*) FROM information_schema.COLUMNS
                    WHERE TABLE_SCHEMA = DATABASE()
                      AND TABLE_NAME = 'emums_character_assets'
                      AND COLUMN_NAME = 'custom_name'
                    """
                )
            )
            if int(col.scalar() or 0) == 0:
                await conn.execute(
                    text(
                        "ALTER TABLE emums_character_assets "
                        "ADD COLUMN custom_name VARCHAR(256) NOT NULL DEFAULT ''"
                    )
                )
            col_type = await conn.execute(
                text(
                    """
                    SELECT DATA_TYPE FROM information_schema.COLUMNS
                    WHERE TABLE_SCHEMA = DATABASE()
                      AND TABLE_NAME = 'emums_audit_profiles'
                      AND COLUMN_NAME = 'snapshot_json'
                    """
                )
            )
            if (col_type.scalar() or "").lower() == "text":
                await conn.execute(
                    text(
                        "ALTER TABLE emums_audit_profiles "
                        "MODIFY COLUMN snapshot_json MEDIUMTEXT NOT NULL"
                    )
                )
            col_sp = await conn.execute(
                text(
                    """
                    SELECT COUNT(*) FROM information_schema.COLUMNS
                    WHERE TABLE_SCHEMA = DATABASE()
                      AND TABLE_NAME = 'emums_character_skill_levels'
                      AND COLUMN_NAME = 'skillpoints_in_skill'
                    """
                )
            )
            if int(col_sp.scalar() or 0) == 0:
                await conn.execute(
                    text(
                        "ALTER TABLE emums_character_skill_levels "
                        "ADD COLUMN skillpoints_in_skill BIGINT NOT NULL DEFAULT 0"
                    )
                )
            await conn.execute(
                text(
                    """
                    CREATE TABLE IF NOT EXISTS emums_hr_role_titles (
                        id INT NOT NULL AUTO_INCREMENT PRIMARY KEY,
                        corporation_id BIGINT NOT NULL,
                        title_id INT NOT NULL,
                        title_name VARCHAR(128) NOT NULL,
                        description VARCHAR(256) NOT NULL DEFAULT '',
                        active TINYINT(1) NOT NULL DEFAULT 1,
                        created_at DATETIME(6) NOT NULL DEFAULT CURRENT_TIMESTAMP(6),
                        INDEX ix_emums_hr_role_titles_corporation_id (corporation_id),
                        INDEX ix_emums_hr_role_titles_title_id (title_id)
                    )
                    """
                )
            )
            await conn.execute(
                text(
                    """
                    CREATE TABLE IF NOT EXISTS emums_character_corp_titles (
                        id INT NOT NULL AUTO_INCREMENT PRIMARY KEY,
                        character_id BIGINT NOT NULL,
                        corporation_id BIGINT NOT NULL,
                        title_id INT NOT NULL,
                        title_name VARCHAR(128) NOT NULL,
                        synced_at DATETIME(6) NULL,
                        INDEX ix_emums_character_corp_titles_character_id (character_id),
                        INDEX ix_emums_character_corp_titles_corporation_id (corporation_id),
                        INDEX ix_emums_character_corp_titles_title_id (title_id)
                    )
                    """
                )
            )
            await conn.execute(
                text(
                    """
                    CREATE TABLE IF NOT EXISTS emums_notification_reads (
                        id INT NOT NULL AUTO_INCREMENT PRIMARY KEY,
                        notification_id INT NOT NULL,
                        character_id BIGINT NOT NULL,
                        read_at DATETIME(6) NOT NULL DEFAULT CURRENT_TIMESTAMP(6),
                        INDEX ix_emums_notification_reads_notification_id (notification_id),
                        INDEX ix_emums_notification_reads_character_id (character_id)
                    )
                    """
                )
            )
            col_recipient = await conn.execute(
                text(
                    """
                    SELECT COUNT(*) FROM information_schema.COLUMNS
                    WHERE TABLE_SCHEMA = DATABASE()
                      AND TABLE_NAME = 'emums_notifications'
                      AND COLUMN_NAME = 'recipient_character_id'
                    """
                )
            )
            if int(col_recipient.scalar() or 0) == 0:
                await conn.execute(
                    text(
                        "ALTER TABLE emums_notifications "
                        "ADD COLUMN recipient_character_id BIGINT NULL, "
                        "ADD INDEX ix_emums_notifications_recipient_character_id (recipient_character_id)"
                    )
                )
            await conn.execute(
                text(
                    """
                    CREATE TABLE IF NOT EXISTS emums_character_interaction_aggregates (
                        id INT NOT NULL AUTO_INCREMENT PRIMARY KEY,
                        owner_user_id INT NOT NULL,
                        character_id BIGINT NOT NULL,
                        counterparty_id BIGINT NOT NULL,
                        counterparty_kind VARCHAR(16) NOT NULL DEFAULT 'entity',
                        counterparty_name VARCHAR(256) NOT NULL DEFAULT '',
                        channel VARCHAR(32) NOT NULL,
                        event_count INT NOT NULL DEFAULT 0,
                        first_seen_at DATETIME(6) NULL,
                        last_seen_at DATETIME(6) NULL,
                        last_detail VARCHAR(512) NOT NULL DEFAULT '',
                        total_amount_isk DECIMAL(20,2) NOT NULL DEFAULT 0,
                        updated_at DATETIME(6) NOT NULL DEFAULT CURRENT_TIMESTAMP(6) ON UPDATE CURRENT_TIMESTAMP(6),
                        UNIQUE KEY uq_char_interaction (character_id, counterparty_id, channel),
                        INDEX ix_emums_char_interaction_owner (owner_user_id),
                        INDEX ix_emums_char_interaction_counterparty (counterparty_id),
                        INDEX ix_emums_char_interaction_kind (counterparty_kind),
                        INDEX ix_emums_char_interaction_last_seen (last_seen_at)
                    )
                    """
                )
            )
            await conn.execute(
                text(
                    """
                    CREATE TABLE IF NOT EXISTS emums_hr_audit_alert_rules (
                        id INT NOT NULL AUTO_INCREMENT PRIMARY KEY,
                        rule_key VARCHAR(64) NOT NULL UNIQUE,
                        name VARCHAR(128) NOT NULL,
                        description TEXT NOT NULL,
                        enabled TINYINT(1) NOT NULL DEFAULT 1,
                        severity VARCHAR(16) NOT NULL DEFAULT 'warn',
                        rule_type VARCHAR(32) NOT NULL,
                        match_json TEXT NOT NULL,
                        webhook_url VARCHAR(512) NOT NULL DEFAULT '',
                        notify_in_app TINYINT(1) NOT NULL DEFAULT 1,
                        cooldown_hours INT NOT NULL DEFAULT 24,
                        created_at DATETIME(6) NOT NULL DEFAULT CURRENT_TIMESTAMP(6),
                        updated_at DATETIME(6) NOT NULL DEFAULT CURRENT_TIMESTAMP(6) ON UPDATE CURRENT_TIMESTAMP(6),
                        INDEX ix_emums_hr_audit_rules_enabled (enabled),
                        INDEX ix_emums_hr_audit_rules_type (rule_type)
                    )
                    """
                )
            )
            await conn.execute(
                text(
                    """
                    CREATE TABLE IF NOT EXISTS emums_hr_audit_alert_events (
                        id INT NOT NULL AUTO_INCREMENT PRIMARY KEY,
                        rule_id INT NULL,
                        character_id BIGINT NOT NULL,
                        character_name VARCHAR(128) NOT NULL DEFAULT '',
                        flag_key VARCHAR(128) NOT NULL,
                        severity VARCHAR(16) NOT NULL DEFAULT 'warn',
                        detail TEXT NOT NULL,
                        webhook_status VARCHAR(32) NOT NULL DEFAULT 'skipped',
                        created_at DATETIME(6) NOT NULL DEFAULT CURRENT_TIMESTAMP(6),
                        INDEX ix_emums_hr_audit_events_rule (rule_id),
                        INDEX ix_emums_hr_audit_events_char (character_id),
                        INDEX ix_emums_hr_audit_events_flag (flag_key),
                        INDEX ix_emums_hr_audit_events_created (created_at)
                    )
                    """
                )
            )
            scale_indexes = [
                (
                    "emums_character_interaction_aggregates",
                    "ix_emums_char_interaction_owner_cp",
                    "owner_user_id, counterparty_id",
                ),
                (
                    "emums_character_interaction_aggregates",
                    "ix_emums_char_interaction_owner_kind",
                    "owner_user_id, counterparty_kind",
                ),
                (
                    "emums_character_wallet_journals",
                    "ix_emums_wallet_journal_char_recorded",
                    "character_id, recorded_at",
                ),
                (
                    "emums_audit_security_flags",
                    "ix_emums_audit_flags_char_key_resolved",
                    "character_id, flag_key, resolved",
                ),
                (
                    "emums_hr_audit_alert_events",
                    "ix_emums_hr_alert_cooldown",
                    "character_id, rule_id, flag_key, created_at",
                ),
            ]
            for table, index_name, columns in scale_indexes:
                tbl = await conn.execute(
                    text(
                        """
                        SELECT COUNT(*) FROM information_schema.TABLES
                        WHERE TABLE_SCHEMA = DATABASE()
                          AND TABLE_NAME = :table_name
                        """
                    ),
                    {"table_name": table},
                )
                if int(tbl.scalar() or 0) == 0:
                    continue
                idx = await conn.execute(
                    text(
                        """
                        SELECT COUNT(*) FROM information_schema.STATISTICS
                        WHERE TABLE_SCHEMA = DATABASE()
                          AND TABLE_NAME = :table_name
                          AND INDEX_NAME = :index_name
                        """
                    ),
                    {"table_name": table, "index_name": index_name},
                )
                if int(idx.scalar() or 0) == 0:
                    await conn.execute(
                        text(f"CREATE INDEX {index_name} ON {table} ({columns})")
                    )
            await conn.execute(
                text(
                    """
                    CREATE TABLE IF NOT EXISTS emums_webhook_notification_rules (
                        id INT NOT NULL AUTO_INCREMENT PRIMARY KEY,
                        owner_user_id INT NOT NULL,
                        created_by_character_id BIGINT NOT NULL,
                        name VARCHAR(128) NOT NULL,
                        description TEXT NOT NULL,
                        enabled TINYINT(1) NOT NULL DEFAULT 1,
                        event_type VARCHAR(64) NOT NULL,
                        match_json TEXT NOT NULL,
                        webhook_url VARCHAR(512) NOT NULL DEFAULT '',
                        notify_in_app TINYINT(1) NOT NULL DEFAULT 1,
                        delivery_mode VARCHAR(16) NOT NULL DEFAULT 'instant',
                        all_characters TINYINT(1) NOT NULL DEFAULT 1,
                        target_character_id BIGINT NULL,
                        last_digest_at DATETIME(6) NULL,
                        created_at DATETIME(6) NOT NULL DEFAULT CURRENT_TIMESTAMP(6),
                        updated_at DATETIME(6) NOT NULL DEFAULT CURRENT_TIMESTAMP(6) ON UPDATE CURRENT_TIMESTAMP(6),
                        INDEX ix_emums_webhook_rules_owner (owner_user_id),
                        INDEX ix_emums_webhook_rules_enabled (enabled),
                        INDEX ix_emums_webhook_rules_event (event_type),
                        INDEX ix_emums_webhook_rules_delivery (delivery_mode)
                    )
                    """
                )
            )
            await conn.execute(
                text(
                    """
                    CREATE TABLE IF NOT EXISTS emums_webhook_notification_pending (
                        id INT NOT NULL AUTO_INCREMENT PRIMARY KEY,
                        rule_id INT NOT NULL,
                        character_id BIGINT NOT NULL,
                        character_name VARCHAR(128) NOT NULL DEFAULT '',
                        event_key VARCHAR(128) NOT NULL,
                        title VARCHAR(256) NOT NULL,
                        body TEXT NOT NULL,
                        payload_json TEXT NOT NULL,
                        created_at DATETIME(6) NOT NULL DEFAULT CURRENT_TIMESTAMP(6),
                        INDEX ix_emums_webhook_pending_rule (rule_id),
                        INDEX ix_emums_webhook_pending_char (character_id),
                        INDEX ix_emums_webhook_pending_key (event_key),
                        INDEX ix_emums_webhook_pending_created (created_at)
                    )
                    """
                )
            )
            await conn.execute(
                text(
                    """
                    CREATE TABLE IF NOT EXISTS emums_webhook_notification_deliveries (
                        id INT NOT NULL AUTO_INCREMENT PRIMARY KEY,
                        rule_id INT NOT NULL,
                        character_id BIGINT NOT NULL,
                        delivery_mode VARCHAR(16) NOT NULL DEFAULT 'instant',
                        event_count INT NOT NULL DEFAULT 1,
                        webhook_status VARCHAR(32) NOT NULL DEFAULT 'skipped',
                        detail TEXT NOT NULL,
                        created_at DATETIME(6) NOT NULL DEFAULT CURRENT_TIMESTAMP(6),
                        INDEX ix_emums_webhook_deliveries_rule (rule_id),
                        INDEX ix_emums_webhook_deliveries_char (character_id),
                        INDEX ix_emums_webhook_deliveries_created (created_at)
                    )
                    """
                )
            )
            await conn.execute(
                text(
                    """
                    CREATE TABLE IF NOT EXISTS emums_srp_rate_rules (
                        id INT NOT NULL AUTO_INCREMENT PRIMARY KEY,
                        label VARCHAR(128) NOT NULL,
                        ship_type_id INT NOT NULL DEFAULT 0,
                        ship_type_name VARCHAR(128) NOT NULL DEFAULT '',
                        doctrine_slug VARCHAR(64) NOT NULL DEFAULT '',
                        base_srp_isk DECIMAL(20, 2) NOT NULL DEFAULT 0,
                        max_percent DECIMAL(6, 2) NULL,
                        doctrine_multiplier DECIMAL(6, 4) NOT NULL DEFAULT 1,
                        meta_multiplier DECIMAL(6, 4) NOT NULL DEFAULT 0.75,
                        shitfit_multiplier DECIMAL(6, 4) NOT NULL DEFAULT 0,
                        allow_shitfit TINYINT(1) NOT NULL DEFAULT 0,
                        enabled TINYINT(1) NOT NULL DEFAULT 1,
                        priority INT NOT NULL DEFAULT 100,
                        created_at DATETIME(6) NOT NULL DEFAULT CURRENT_TIMESTAMP(6),
                        INDEX ix_emums_srp_rate_ship (ship_type_id),
                        INDEX ix_emums_srp_rate_doctrine (doctrine_slug),
                        INDEX ix_emums_srp_rate_enabled (enabled)
                    )
                    """
                )
            )
            srp_cols = [
                ("killmail_hash", "VARCHAR(64) NOT NULL DEFAULT ''"),
                ("ship_type_id", "INT NOT NULL DEFAULT 0"),
                ("fit_json", "TEXT NOT NULL"),
                ("fit_grade", "VARCHAR(16) NOT NULL DEFAULT 'shitfit'"),
                ("doctrine_slug", "VARCHAR(64) NOT NULL DEFAULT ''"),
                ("doctrine_match_pct", "FLOAT NOT NULL DEFAULT 0"),
                ("submitted_notes", "TEXT NOT NULL"),
                ("solar_system_name", "VARCHAR(128) NOT NULL DEFAULT ''"),
                ("killed_at", "DATETIME(6) NULL"),
                ("submitted_at", "DATETIME(6) NULL"),
            ]
            srp_table = await conn.execute(
                text(
                    """
                    SELECT COUNT(*) FROM information_schema.TABLES
                    WHERE TABLE_SCHEMA = DATABASE()
                      AND TABLE_NAME = 'emums_srp_losses'
                    """
                )
            )
            if int(srp_table.scalar() or 0) > 0:
                for col_name, col_def in srp_cols:
                    col = await conn.execute(
                        text(
                            """
                            SELECT COUNT(*) FROM information_schema.COLUMNS
                            WHERE TABLE_SCHEMA = DATABASE()
                              AND TABLE_NAME = 'emums_srp_losses'
                              AND COLUMN_NAME = :col_name
                            """
                        ),
                        {"col_name": col_name},
                    )
                    if int(col.scalar() or 0) == 0:
                        if col_def.startswith("TEXT NOT NULL"):
                            await conn.execute(
                                text(f"ALTER TABLE emums_srp_losses ADD COLUMN {col_name} TEXT NULL")
                            )
                            await conn.execute(
                                text(
                                    f"UPDATE emums_srp_losses SET {col_name} = '' "
                                    f"WHERE {col_name} IS NULL"
                                )
                            )
                            await conn.execute(
                                text(
                                    f"ALTER TABLE emums_srp_losses "
                                    f"MODIFY COLUMN {col_name} TEXT NOT NULL"
                                )
                            )
                        else:
                            await conn.execute(
                                text(f"ALTER TABLE emums_srp_losses ADD COLUMN {col_name} {col_def}")
                            )
                idx_fit = await conn.execute(
                    text(
                        """
                        SELECT COUNT(*) FROM information_schema.STATISTICS
                        WHERE TABLE_SCHEMA = DATABASE()
                          AND TABLE_NAME = 'emums_srp_losses'
                          AND INDEX_NAME = 'ix_emums_srp_losses_fit_grade'
                        """
                    )
                )
                if int(idx_fit.scalar() or 0) == 0:
                    await conn.execute(
                        text("CREATE INDEX ix_emums_srp_losses_fit_grade ON emums_srp_losses (fit_grade)")
                    )

            for table, col_name, col_def in [
                ("emums_fittings", "owner_character_id", "BIGINT NULL"),
                ("emums_fittings", "owner_character_name", "VARCHAR(128) NOT NULL DEFAULT ''"),
                ("emums_fittings", "esi_fitting_id", "BIGINT NULL"),
                ("emums_indy_blueprints", "owner_character_id", "BIGINT NULL"),
                ("emums_indy_blueprints", "item_id", "BIGINT NULL"),
                ("emums_authed_structures", "structure_type_id", "INT NOT NULL DEFAULT 0"),
                ("emums_authed_structures", "structure_type_name", "VARCHAR(128) NOT NULL DEFAULT ''"),
                ("emums_authed_structures", "structure_state", "VARCHAR(32) NOT NULL DEFAULT ''"),
                ("emums_authed_structures", "fuel_expires_at", "DATETIME(6) NULL"),
                ("emums_authed_structures", "fuel_blocks_qty", "INT NOT NULL DEFAULT 0"),
                ("emums_authed_structures", "corporation_id", "BIGINT NOT NULL DEFAULT 0"),
            ]:
                col = await conn.execute(
                    text(
                        """
                        SELECT COUNT(*) FROM information_schema.COLUMNS
                        WHERE TABLE_SCHEMA = DATABASE()
                          AND TABLE_NAME = :table_name
                          AND COLUMN_NAME = :col_name
                        """
                    ),
                    {"table_name": table, "col_name": col_name},
                )
                if int(col.scalar() or 0) == 0:
                    await conn.execute(text(f"ALTER TABLE {table} ADD COLUMN {col_name} {col_def}"))

            for table, index_name, columns in [
                ("emums_fittings", "ix_emums_fittings_owner_character_id", "owner_character_id"),
                ("emums_fittings", "ix_emums_fittings_esi_fitting_id", "esi_fitting_id"),
                ("emums_indy_blueprints", "ix_emums_indy_blueprints_owner_character_id", "owner_character_id"),
                ("emums_indy_blueprints", "ix_emums_indy_blueprints_item_id", "item_id"),
            ]:
                tbl = await conn.execute(
                    text(
                        """
                        SELECT COUNT(*) FROM information_schema.TABLES
                        WHERE TABLE_SCHEMA = DATABASE() AND TABLE_NAME = :table_name
                        """
                    ),
                    {"table_name": table},
                )
                if int(tbl.scalar() or 0) == 0:
                    continue
                idx = await conn.execute(
                    text(
                        """
                        SELECT COUNT(*) FROM information_schema.STATISTICS
                        WHERE TABLE_SCHEMA = DATABASE()
                          AND TABLE_NAME = :table_name
                          AND INDEX_NAME = :index_name
                        """
                    ),
                    {"table_name": table, "index_name": index_name},
                )
                if int(idx.scalar() or 0) == 0:
                    unique = "UNIQUE " if "esi_fitting_id" in index_name or "item_id" in index_name else ""
                    await conn.execute(
                        text(f"CREATE {unique}INDEX {index_name} ON {table} ({columns})")
                    )

            tbl_exists = await conn.execute(
                text(
                    """
                    SELECT COUNT(*) FROM information_schema.TABLES
                    WHERE TABLE_SCHEMA = DATABASE() AND TABLE_NAME = 'emums_character_market_orders'
                    """
                )
            )
            if int(tbl_exists.scalar() or 0) == 0:
                await conn.execute(
                    text(
                        """
                        CREATE TABLE emums_character_market_orders (
                            id INT NOT NULL AUTO_INCREMENT PRIMARY KEY,
                            character_id BIGINT NOT NULL,
                            character_name VARCHAR(128) NOT NULL DEFAULT '',
                            order_id BIGINT NOT NULL,
                            type_id INT NOT NULL,
                            type_name VARCHAR(256) NOT NULL,
                            is_buy_order TINYINT(1) NOT NULL DEFAULT 0,
                            price DECIMAL(16,2) NOT NULL DEFAULT 0,
                            volume_remain INT NOT NULL DEFAULT 0,
                            volume_total INT NOT NULL DEFAULT 0,
                            min_volume INT NOT NULL DEFAULT 0,
                            location_id BIGINT NOT NULL DEFAULT 0,
                            location_name VARCHAR(256) NOT NULL DEFAULT '',
                            range_label VARCHAR(64) NOT NULL DEFAULT '',
                            issued_at DATETIME(6) NULL,
                            duration_days INT NOT NULL DEFAULT 0,
                            is_corporation TINYINT(1) NOT NULL DEFAULT 0,
                            updated_at DATETIME(6) NOT NULL DEFAULT CURRENT_TIMESTAMP(6)
                                ON UPDATE CURRENT_TIMESTAMP(6),
                            UNIQUE KEY uq_emums_character_market_orders_order_id (order_id),
                            KEY ix_emums_character_market_orders_character_id (character_id),
                            KEY ix_emums_character_market_orders_type_id (type_id)
                        )
                        """
                    )
                )

            for table, col_name, col_def in [
                ("emums_indy_job_records", "owner_character_id", "BIGINT NULL"),
                ("emums_indy_job_records", "job_id", "BIGINT NULL"),
                ("emums_indy_job_records", "facility_id", "BIGINT NULL"),
                ("emums_indy_job_records", "installer_id", "BIGINT NULL"),
                ("emums_indy_job_records", "installer_name", "VARCHAR(128) NOT NULL DEFAULT ''"),
                ("emums_indy_job_records", "started_at", "DATETIME(6) NULL"),
                ("emums_mining_logs", "source", "VARCHAR(16) NOT NULL DEFAULT 'seed'"),
                ("emums_mining_logs", "system_id", "INT NULL"),
            ]:
                col = await conn.execute(
                    text(
                        """
                        SELECT COUNT(*) FROM information_schema.COLUMNS
                        WHERE TABLE_SCHEMA = DATABASE()
                          AND TABLE_NAME = :table_name
                          AND COLUMN_NAME = :col_name
                        """
                    ),
                    {"table_name": table, "col_name": col_name},
                )
                if int(col.scalar() or 0) == 0:
                    await conn.execute(text(f"ALTER TABLE {table} ADD COLUMN {col_name} {col_def}"))

            for table, index_name, columns in [
                ("emums_indy_job_records", "ix_emums_indy_job_records_owner_character_id", "owner_character_id"),
                ("emums_indy_job_records", "ix_emums_indy_job_records_job_id", "job_id"),
                ("emums_indy_job_records", "ix_emums_indy_job_records_installer_id", "installer_id"),
                ("emums_mining_logs", "ix_emums_mining_logs_source", "source"),
            ]:
                tbl = await conn.execute(
                    text(
                        """
                        SELECT COUNT(*) FROM information_schema.TABLES
                        WHERE TABLE_SCHEMA = DATABASE() AND TABLE_NAME = :table_name
                        """
                    ),
                    {"table_name": table},
                )
                if int(tbl.scalar() or 0) == 0:
                    continue
                idx = await conn.execute(
                    text(
                        """
                        SELECT COUNT(*) FROM information_schema.STATISTICS
                        WHERE TABLE_SCHEMA = DATABASE()
                          AND TABLE_NAME = :table_name
                          AND INDEX_NAME = :index_name
                        """
                    ),
                    {"table_name": table, "index_name": index_name},
                )
                if int(idx.scalar() or 0) == 0:
                    await conn.execute(
                        text(f"CREATE INDEX {index_name} ON {table} ({columns})")
                    )

            for ddl in _STOREFRONT_TABLES_DDL:
                await conn.execute(text(ddl))

            for ddl in _ONBOARDING_TABLES_DDL:
                await conn.execute(text(ddl))

            for ddl in _INTEL_TAGS_DDL:
                await conn.execute(text(ddl))

            # Character assets: allow same item_id across characters (corp hangar seen by multiple alts).
            asset_tbl = await conn.execute(
                text(
                    """
                    SELECT COUNT(*) FROM information_schema.TABLES
                    WHERE TABLE_SCHEMA = DATABASE() AND TABLE_NAME = 'emums_character_assets'
                    """
                )
            )
            if int(asset_tbl.scalar() or 0) > 0:
                old_uq = await conn.execute(
                    text(
                        """
                        SELECT COUNT(*) FROM information_schema.STATISTICS
                        WHERE TABLE_SCHEMA = DATABASE()
                          AND TABLE_NAME = 'emums_character_assets'
                          AND INDEX_NAME = 'ix_emums_character_assets_item_id'
                          AND NON_UNIQUE = 0
                        """
                    )
                )
                if int(old_uq.scalar() or 0) > 0:
                    await conn.execute(text("ALTER TABLE emums_character_assets DROP INDEX ix_emums_character_assets_item_id"))
                    await conn.execute(
                        text("CREATE INDEX ix_emums_character_assets_item_id ON emums_character_assets (item_id)")
                    )
                new_uq = await conn.execute(
                    text(
                        """
                        SELECT COUNT(*) FROM information_schema.TABLE_CONSTRAINTS
                        WHERE TABLE_SCHEMA = DATABASE()
                          AND TABLE_NAME = 'emums_character_assets'
                          AND CONSTRAINT_NAME = 'uq_emums_character_assets_char_item'
                        """
                    )
                )
                if int(new_uq.scalar() or 0) == 0:
                    await conn.execute(
                        text(
                            "ALTER TABLE emums_character_assets "
                            "ADD CONSTRAINT uq_emums_character_assets_char_item UNIQUE (character_id, item_id)"
                        )
                    )
    finally:
        await engine.dispose()


def main() -> int:
    import asyncio

    if asyncio.run(_needs_stamp()):
        print("EMUMS: existing schema without alembic_version — stamping head")
        stamp = subprocess.run(["alembic", "stamp", "head"], check=False)
        if stamp.returncode != 0:
            print("EMUMS: stamp skipped (likely already applied by another instance)")

    result = subprocess.run(["alembic", "upgrade", "head"], check=False)
    if result.returncode != 0:
        print("EMUMS: alembic upgrade failed", file=sys.stderr)
        return result.returncode
    asyncio.run(_ensure_schema_extras())
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
