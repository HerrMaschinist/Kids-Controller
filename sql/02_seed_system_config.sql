-- =============================================================================
-- 02_seed_system_config.sql
-- KIDS_CONTROLLER – initiale system_config-Einträge
-- =============================================================================
-- Ausführung: psql -h 192.168.50.10 -U kids_controller_admin -d kids_controller
--             -f 02_seed_system_config.sql
-- =============================================================================
-- Hinweis: updated_at wird explizit gesetzt (kein Trigger, kein DEFAULT-Fallback)
-- =============================================================================

INSERT INTO system_config (key_name, value, updated_at)
VALUES
    ('algorithm_version',      '1.0.0',                    CURRENT_TIMESTAMP),
    ('shuffle_algorithm',      'fisher_yates',             CURRENT_TIMESTAMP),
    ('window_size',            '12',                       CURRENT_TIMESTAMP),
    ('timezone',               'Europe/Berlin',            CURRENT_TIMESTAMP),
    ('api_version',            'v1',                       CURRENT_TIMESTAMP),
    ('kids_ids',               '1=Leon,2=Emmi,3=Elsa',    CURRENT_TIMESTAMP)
ON CONFLICT (key_name) DO UPDATE
    SET value      = EXCLUDED.value,
        updated_at = CURRENT_TIMESTAMP;
