# KIDS_CONTROLLER – Architektur

## Überblick

KIDS_CONTROLLER ist ein schichtenarchitekturiertes Python-Backend, das auf einem
Raspberry Pi läuft und über FastAPI eine HTTP-Schnittstelle für Home Assistant bereitstellt.

```
Home Assistant
     │
     │ POST /api/v1/draw
     ▼
┌────────────────────────────────────────────────┐
│  app/                                          │
│  ├── main.py          Anwendungseinstieg       │
│  ├── api_routes.py    FastAPI-Router           │
│  └── dependencies.py  Dependency Injection     │
└────────────────────────┬───────────────────────┘
                         │
┌────────────────────────▼───────────────────────┐
│  integrations/                                 │
│  ├── homeassistant_models.py  Pydantic-Modelle │
│  ├── homeassistant_adapter.py HA ↔ Domäne      │
│  ├── router_client.py        Optionaler Router │
│  └── supervisor_models.py    Statusschema      │
└────────────────────────┬───────────────────────┘
                         │
┌────────────────────────▼───────────────────────┐
│  core/                                         │
│  ├── models.py        Domänenobjekte           │
│  ├── algorithm.py     Auslosungsalgorithmus    │
│  ├── draw_service.py  Orchestrierung           │
│  ├── supervisor_state.py  Laufzeitstatus       │
│  ├── supervisor_service.py  Status-/Health-API │
│  └── validation.py    Eingabeprüfung          │
└────────────────────────┬───────────────────────┘
                         │
┌────────────────────────▼───────────────────────┐
│  persistence/                                  │
│  ├── postgres_client.py  psycopg v3 Conninfo   │
│  ├── repositories.py     Datenbankzugriff      │
│  └── mappers.py          Row-Dict ↔ Domäne     │
└────────────────────────┬───────────────────────┘
                         │
                 PostgreSQL 14+
              192.168.50.10:5432
              Datenbank: kids_controller
```

---

## Schichten

### app/

Enthält die FastAPI-Anwendung. `main.py` startet den psycopg v3 Connection-Pool beim
Hochfahren und schließt ihn beim Herunterfahren. `api_routes.py` registriert ausschließlich
den Endpunkt `POST /api/v1/draw` und einen Liveness-Check. `dependencies.py`
instantiiert Repositories und DrawService via FastAPI-Dependency-Injection.

### integrations/

Adapter-Schicht für Home Assistant. Kapselt die Pydantic-Modelle (`HaDrawRequest`,
`HaDrawResponse`) und die Konvertierungslogik vollständig von der Domäne. Das
Antwortfeld `date` ist intern `draw_date` und wird via Pydantic-Alias als `"date"`
in der JSON-Antwort serialisiert. Zusätzlich wird `generated_at` aus `draw.draw_ts`
an Home Assistant zurückgegeben, damit die Anzeige den echten Persistierungszeitpunkt
des Draws zeigen kann.

### core/

Die gesamte Fachlogik: Domänenobjekte (`models.py`), Algorithmus (`algorithm.py`),
Transaktionsorchestrierung (`draw_service.py`) und Validierung (`validation.py`).
Keine Datenbankabhängigkeiten. Kein Import aus `app/` oder `integrations/`.

### persistence/

psycopg v3 basierter Datenbankzugriff mit direkter `AsyncConnection` und `dict_row`.
`WindowRepository` verwaltet den Transaktionskontext (`SELECT FOR UPDATE`).
`DrawRepository` schreibt Draws und liest per `request_id` bzw. Datum.
`mappers.py` konvertiert psycopg v3 dict-Rows 1:1 zu Domänenobjekten; Feldnamen
entsprechen exakt den SQL-Spaltennamen.

`draw_service.py` bleibt der deterministische Kern. Der optionale Router-Client
liefert nur Beobachtung, Bewertung und Fehlersignale; er überschreibt nie die
Auslosung.

Router-Regeln:
- nur explizit konfigurierte Basis-URL plus fixer Beobachtungspfad
- standardmäßig deaktiviert
- read-only/supervisorisch
- keine DB-Schreibrechte
- harte Timeouts und strikte Antwortvalidierung
- Authentifizierung per `X-API-Key` gegen den lokalen PI-Guardian-Router
- Fehlschläge degradieren nur den Router-Pfad, nicht den Kern

### config/

Konfiguration via Pydantic-Settings (Umgebungsvariablen / `.env`). Logging-Setup.

---

## Transaktionsbefehl

Die Draw-Operation läuft in einer einzigen PostgreSQL-Transaktion:

1. `SELECT * FROM fairness_windows WHERE window_status = 'ACTIVE' FOR UPDATE`
2. Algorithmus berechnet Draw und ggf. aktualisierten FairnessWindow
3. Falls ein neues Fenster nötig ist: `INSERT INTO fairness_windows ...` vor dem Draw
4. `INSERT INTO draws ...`
5. Commit – bei Fehler automatischer Rollback

Alle Schritte 1–4 laufen über dieselbe `psycopg.AsyncConnection` innerhalb von
`async with conn.transaction()`.

---

## Idempotenz

Jede `request_id` wird vor der Berechnung gegen die `draws`-Tabelle geprüft.
Bei Duplikat wird der vorhandene Draw zurückgegeben – ohne erneute Berechnung
und ohne Transaktion. Zusätzlich wird ein Konflikt auf die effektive Tageszeile
(`uq_effective_draw_per_date`) als bestehender Tages-Draw behandelt.

PAIR-Runtime-Wahrheit liegt ausschließlich in `core/draw_service.py::_handle_pair()`.

Die neue Statusschicht liest den aktuellen Fensterzustand und den letzten
effektiven Draw aus der DB und ergänzt ihn um den in-memory Supervisor-Status.
Der Statuspfad ist lesend und schreibt keine fachlichen Daten.

---

## Kinder-IDs

| ID | Name |
|---|---|
| 1 | Leon |
| 2 | Emmi |
| 3 | Elsa |

---

## Trennung von filabase

`filabase` und `filabase_admin` werden weder in SQL-Skripten noch im Python-Code
referenziert. Das Reset-Skript `00_reset_and_create_database.sql` berührt
ausschließlich `kids_controller` und `kids_controller_admin`.
