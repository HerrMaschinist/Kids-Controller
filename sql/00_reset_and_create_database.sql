-- =============================================================================
-- 00_reset_and_create_database.sql
-- KIDS_CONTROLLER – Datenbank- und Rollen-Reset
-- =============================================================================
-- WICHTIG: Dieses Skript berührt ausschließlich kids_controller und
--          kids_controller_admin.
--          filabase und filabase_admin bleiben vollständig unangetastet.
-- =============================================================================
-- Ausführung: psql -h 192.168.50.10 -U <pg-superuser> -f 00_reset_and_create_database.sql
-- Hinweis: <pg-superuser> ist der PostgreSQL-Superuser der Zielinstanz,
--          typischerweise der Systembenutzer, unter dem der Cluster läuft.
-- =============================================================================

-- Verbindungen zur Datenbank kids_controller trennen, falls vorhanden
SELECT pg_terminate_backend(pid)
FROM   pg_stat_activity
WHERE  datname = 'kids_controller'
  AND  pid <> pg_backend_pid();

-- Datenbank droppen (falls vorhanden)
DROP DATABASE IF EXISTS kids_controller;

-- Rolle droppen (falls vorhanden)
DROP ROLE IF EXISTS kids_controller_admin;

-- Rolle anlegen
CREATE ROLE kids_controller_admin
    WITH LOGIN
    PASSWORD 'kc_secure_pw_change_me'
    NOSUPERUSER
    NOCREATEDB
    NOCREATEROLE
    NOINHERIT
    NOREPLICATION;

-- Datenbank anlegen ohne fixe Locale-Angabe.
-- Verwendet die Systemlocale des PostgreSQL-Clusters, was auf jedem
-- Raspberry-Pi-Setup ohne Voraussetzungen funktioniert.
CREATE DATABASE kids_controller
    WITH OWNER    = kids_controller_admin
         ENCODING = 'UTF8'
         TEMPLATE = template1;

COMMENT ON DATABASE kids_controller IS
    'KIDS_CONTROLLER – faire Reihenfolgeberechnung für Leon, Emmi und Elsa';
