# KIDS_CONTROLLER

Faire, revisionssichere Reihenfolgeberechnung für **Leon** (1), **Emmi** (2) und **Elsa** (3).

Das System berechnet täglich eine Reihenfolge basierend auf Anwesenheit und einem
Fairness-Algorithmus. Es läuft auf einem Raspberry Pi, speichert alle Ergebnisse
revisionssicher in PostgreSQL und stellt einen FastAPI-Endpunkt für Home Assistant bereit.

---

## Voraussetzungen

- Python 3.11+
- PostgreSQL 14+ unter `192.168.50.10:5432`
- Datenbank `kids_controller` und Rolle `kids_controller_admin` (via SQL-Skripte anlegen)

---

## Einrichtung

### 1. Datenbank aufbauen

```bash
# Als PostgreSQL-Superuser (z.B. postgres):
psql -h 192.168.50.10 -U postgres -f sql/00_reset_and_create_database.sql

# Als kids_controller_admin:
psql -h 192.168.50.10 -U kids_controller_admin -d kids_controller \
     -f sql/01_schema_types_and_tables.sql

psql -h 192.168.50.10 -U kids_controller_admin -d kids_controller \
     -f sql/02_seed_system_config.sql
```

### 2. Python-Abhängigkeiten installieren

```bash
cd /opt/kids_controller
pip install -e ".[test]"
```

### 3. Konfiguration

Die produktive Konfiguration liegt in `/etc/kids_controller/.env`.
Ein Beispiel für neue Setups liegt im Repo unter `.env.example`.

```env
DB_HOST=192.168.50.10
DB_PORT=5432
DB_NAME=kids_controller
DB_USER=kids_controller_admin
DB_PASSWORD=kc_secure_pw_change_me
API_PORT=8001
ROUTER_ENABLED=false
ROUTER_URL=http://127.0.0.1:8071
ROUTER_API_KEY=<<from secure env only>>
ROUTER_TIMEOUT_SECONDS=2.0
ROUTER_OBSERVE_PATH=/route
```

Der Router ist optional und rein supervisorisch. Er bekommt nur minimierte
Beobachtungsdaten, authentifiziert sich per `X-API-Key`, liefert nur
Bewertung/Warnung/Anomaliehinweise zurück und darf weder den Draw überschreiben
noch direkt in die Fach-Tabellen schreiben.

### 4. Server starten

```bash
python -m app.main
# oder
uvicorn app.main:app --host 0.0.0.0 --port 8001
```

### 5. Als systemd-Dienst

```ini
[Unit]
Description=KIDS_CONTROLLER FastAPI Service
After=network.target

[Service]
WorkingDirectory=/opt/kids_controller
ExecStart=/usr/bin/python -m app.main
Restart=on-failure
User=pi

[Install]
WantedBy=multi-user.target
```

## Deployment

- Quellstand: `/home/alex/kids_controller`
- Live-Deployment: `/opt/kids_controller`
- Versionierte systemd-Unit: `/home/alex/kids_controller/deploy/systemd/kids-controller.service`
- Deploy: `sudo bash /home/alex/kids_controller/scripts/deploy.sh`
- Drift-Prüfung: `bash /home/alex/kids_controller/scripts/check_drift.sh`
- Live-Verifikation: `bash /home/alex/kids_controller/scripts/verify_live.sh`

Mehr Details stehen in [DEPLOYMENT.md](/home/alex/kids_controller/docs/DEPLOYMENT.md).

---

## Tests ausführen

```bash
cd /opt/kids_controller
python -m pytest tests/ -v
```

---

## API-Endpunkt

```
POST http://localhost:8001/api/v1/draw
Content-Type: application/json

{
  "leon_present": true,
  "emmi_present": true,
  "elsa_present": false,
  "request_id": "550e8400-e29b-41d4-a716-446655440000"
}
```

Antwort:

```json
{
  "draw_id": 42,
  "mode": "PAIR",
  "pos1": 1,
  "pos2": 2,
  "pos3": null,
  "stop_morning": 1,
  "stop_midday": 2,
  "date": "2025-01-15",
  "generated_at": "2025-01-15T06:42:17Z"
}
```

Zusätzlich gibt es einen lesenden Status-Endpunkt:

```bash
GET /api/v1/status
```

---

## Wichtige Hinweise

- `filabase` und `filabase_admin` werden von keinem Skript und keinem Code berührt.
- Die Anwesenheits-Felder heißen exakt `leon_present`, `emmi_present`, `elsa_present`.
- Der Name lautet **Emmi** – diese Schreibweise ist verbindlich.
- Das Antwortfeld `date` wird intern als `draw_date` geführt und via Pydantic-Alias als `date` serialisiert.
