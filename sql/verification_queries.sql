-- =============================================================================
-- verification_queries.sql
-- KIDS_CONTROLLER – Verifikationsabfragen nach Datenbankaufbau
-- =============================================================================

-- 1. Prüfe ENUM-Typen
SELECT   typname, enumlabel, enumsortorder
FROM     pg_enum e
JOIN     pg_type t ON e.enumtypid = t.oid
WHERE    typname IN ('window_status_enum','mode_enum','perm_code_enum','pair_key_enum')
ORDER BY typname, enumsortorder;

-- 2. Prüfe Tabellen-Existenz
SELECT   table_name
FROM     information_schema.tables
WHERE    table_schema = 'public'
  AND    table_name IN ('fairness_windows','draws','system_config')
ORDER BY table_name;

-- 2b. Prüfe Unique-Indizes/FKs wie im Live-Stand
SELECT   indexname, indexdef
FROM     pg_indexes
WHERE    schemaname = 'public'
  AND    tablename IN ('fairness_windows', 'draws')
  AND    indexname IN (
            'uq_active_window',
            'uq_fairness_windows_window_id',
            'uq_draws_request_id',
            'uq_effective_draw_per_date',
            'idx_draws_draw_date_mode',
            'idx_draws_draw_date_window'
         )
ORDER BY tablename, indexname;

SELECT   conname, contype, pg_get_constraintdef(oid) AS definition
FROM     pg_constraint
WHERE    conrelid IN ('draws'::regclass, 'fairness_windows'::regclass)
ORDER BY conname;

-- 3. Prüfe Spalten von fairness_windows
SELECT   column_name, data_type, udt_name, is_nullable, column_default
FROM     information_schema.columns
WHERE    table_schema = 'public'
  AND    table_name   = 'fairness_windows'
ORDER BY ordinal_position;

-- 4. Prüfe Spalten von draws
SELECT   column_name, data_type, udt_name, is_nullable, column_default
FROM     information_schema.columns
WHERE    table_schema = 'public'
  AND    table_name   = 'draws'
ORDER BY ordinal_position;

-- 5. Prüfe Spalten von system_config
SELECT   column_name, data_type, udt_name, is_nullable, column_default
FROM     information_schema.columns
WHERE    table_schema = 'public'
  AND    table_name   = 'system_config'
ORDER BY ordinal_position;

-- 6. Prüfe replay_context_hash in draws
SELECT   column_name, data_type, udt_name, is_nullable, column_default
FROM     information_schema.columns
WHERE    table_schema = 'public'
  AND    table_name   = 'draws'
  AND    column_name  = 'replay_context_hash';

-- 7. Prüfe system_config-Inhalt
SELECT key_name, value, updated_at
FROM   system_config
ORDER BY key_name;

-- 8. Prüfe window_status_enum enthält kein ABORTED
SELECT enumlabel
FROM   pg_enum e
JOIN   pg_type t ON e.enumtypid = t.oid
WHERE  typname = 'window_status_enum';
-- Erwartetes Ergebnis: nur 'ACTIVE' und 'COMPLETED'

-- 8. Prüfe present_mask-Typ in draws (muss SMALLINT sein, kein JSON/JSONB)
SELECT column_name, data_type, udt_name
FROM   information_schema.columns
WHERE  table_schema = 'public'
  AND  table_name   = 'draws'
  AND  column_name  = 'present_mask';
-- Erwartetes Ergebnis: data_type = 'smallint'

-- 9. Prüfe request_id NOT NULL
SELECT column_name, is_nullable
FROM   information_schema.columns
WHERE  table_schema = 'public'
  AND  table_name   = 'draws'
  AND  column_name  = 'request_id';
-- Erwartetes Ergebnis: is_nullable = 'NO'

-- 10. Prüfe window_index nullable in draws
SELECT column_name, is_nullable
FROM   information_schema.columns
WHERE  table_schema = 'public'
  AND  table_name   = 'draws'
  AND  column_name  = 'window_index';
-- Erwartetes Ergebnis: is_nullable = 'YES'

-- 11. Prüfe window_id CHAR(8) in fairness_windows
SELECT column_name, data_type, character_maximum_length
FROM   information_schema.columns
WHERE  table_schema = 'public'
  AND  table_name   = 'fairness_windows'
  AND  column_name  = 'window_id';
-- Erwartetes Ergebnis: character_maximum_length = 8

-- 12. Prüfe last_full_order Typ (perm_code_enum)
SELECT column_name, udt_name, is_nullable
FROM   information_schema.columns
WHERE  table_schema = 'public'
  AND  table_name   = 'fairness_windows'
  AND  column_name  = 'last_full_order';
-- Erwartetes Ergebnis: udt_name = 'perm_code_enum', is_nullable = 'YES'

-- 13. Alle Constraints auf draws
SELECT conname, contype, pg_get_constraintdef(oid) AS definition
FROM   pg_constraint
WHERE  conrelid = 'draws'::regclass
ORDER BY conname;
