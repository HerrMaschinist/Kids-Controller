-- =============================================================================
-- 03_add_replay_context_hash.sql
-- KIDS_CONTROLLER – Migration für replay_context_hash
-- =============================================================================
-- Zweck:
--   Ergänzt bestehende draws-Tabellen um replay_context_hash und füllt historische
--   Zeilen mit dem bereits vorhandenen seed_material_hash als kompatiblem Fallback.
--
-- Hinweis:
--   Für neue Installationen ist replay_context_hash bereits Teil von
--   01_schema_types_and_tables.sql.
-- =============================================================================

ALTER TABLE draws
    ADD COLUMN IF NOT EXISTS replay_context_hash CHAR(64);

UPDATE draws
SET    replay_context_hash = seed_material_hash
WHERE  replay_context_hash IS NULL;

ALTER TABLE draws
    ALTER COLUMN replay_context_hash SET NOT NULL;

COMMENT ON COLUMN draws.replay_context_hash IS
    'SHA-256 des normalisierten Replay-Kontexts';
