# KIDS_CONTROLLER – API-Dokumentation

## Basis-URL

```
http://<raspberry-pi-ip>:8001
```

---

## Endpunkte

### POST /api/v1/draw

Berechnet die Reihenfolge für den aktuellen Tag basierend auf Anwesenheit der Kinder.

**Idempotenz:** Gleiche `request_id` liefert immer dasselbe Ergebnis.
Zusätzlich ist pro Kalendertag nur ein effektiver Draw zulässig.

#### Request

```http
POST /api/v1/draw
Content-Type: application/json
```

```json
{
  "leon_present": true,
  "emmi_present": true,
  "elsa_present": false,
  "request_id": "550e8400-e29b-41d4-a716-446655440000"
}
```

| Feld | Typ | Pflicht | Beschreibung |
|---|---|---|---|
| `leon_present` | boolean | ja | Leon ist heute anwesend |
| `emmi_present` | boolean | ja | Emmi ist heute anwesend |
| `elsa_present` | boolean | ja | Elsa ist heute anwesend |
| `request_id` | UUID | ja | Eindeutige Request-ID; niemals leer |

**Feldnamen sind verbindlich.** Das Feld heißt exakt `emmi_present`.

#### Response 200

```json
{
  "draw_id": 42,
  "mode": "PAIR",
  "pos1": 1,
  "pos2": 2,
  "pos3": null,
  "stop_morning": 1,
  "stop_midday": 2,
  "date": "2025-01-15"
}
```

| Feld | Typ | Beschreibung |
|---|---|---|
| `draw_id` | integer | Primärschlüssel des Draws |
| `mode` | string | `TRIPLET`, `PAIR`, `SINGLE` oder `SKIP` |
| `pos1` | integer\|null | Kind-ID auf Position 1 |
| `pos2` | integer\|null | Kind-ID auf Position 2 |
| `pos3` | integer\|null | Kind-ID auf Position 3 (nur TRIPLET) |
| `stop_morning` | integer\|null | Kind-ID Haltestelle morgens |
| `stop_midday` | integer\|null | Kind-ID Haltestelle mittags |
| `date` | string (ISO 8601) | Datum des Draws |

**Alias-Hinweis:** Das Feld `date` in der JSON-Antwort entspricht intern dem Python-Feld
`draw_date` in `HaDrawResponse`. Der Alias `date` wird via Pydantic gesetzt und ist
die externe API-Wahrheit.

#### Kind-IDs in der Antwort

| ID | Name |
|---|---|
| 1 | Leon |
| 2 | Emmi |
| 3 | Elsa |

#### Response 422 – Validierungsfehler

```json
{
  "field": "request_id",
  "message": "request_id darf nicht die Null-UUID sein"
}
```

#### Response 500 – Interner Fehler

```json
{
  "detail": "Interner Serverfehler"
}
```

---

### GET /api/v1/health

Liveness-Check.

```json
{
  "status": "ok",
  "service": "kids_controller"
}
```

---

### GET /api/v1/status

Lesbarer Betriebsstatus für Supervisor-/Router-Überwachung.

```json
{
  "status": "ok",
  "active_window_id": "92JJE8PS",
  "active_window_status": "ACTIVE",
  "active_window_index": 9,
  "last_successful_draw_id": 123,
  "last_successful_draw_date": "2026-04-15",
  "last_successful_draw_mode": "TRIPLET",
  "last_successful_draw_generated_at": "2026-04-15T00:01:00Z",
  "last_run_at": "2026-04-15T01:00:00Z",
  "last_error_at": null,
  "last_error_source": null,
  "last_error_message": null,
  "router": {
    "enabled": false,
    "available": null,
    "last_checked_at": null,
    "last_probe_status": null,
    "last_probe_message": null,
    "last_probe_error": null,
    "last_assessment_status": null,
    "last_assessment_message": null,
    "last_assessment_findings": [],
    "last_assessment_recommendations": [],
    "last_assessment_confidence": null,
    "last_assessment_source": null,
    "last_assessment_at": null
  },
  "invariants": {
    "exactly_one_active_window": true,
    "active_window_present": true,
    "latest_effective_draw_present": true,
    "last_error_present": false
  }
}
```

Der Status-Endpunkt ist lesend. Er verändert weder Draws noch Fenster.

Der Router ist read-only und supervisorisch:
- akzeptiert nur eine konfigurierte Basis-URL plus festen Beobachtungspfad `/route`
- sendet nur minimierte Beobachtungsdaten
- authentifiziert sich per `X-API-Key`
- akzeptiert nur strikt validierte JSON-Antworten
- schreibt nie in die Kern-DB
- fällt bei Fehlern in einen degradierten, aber sicheren Zustand zurück

---

## Home-Assistant-Integration (Beispiel)

```yaml
rest_command:
  kids_draw:
    url: "http://192.168.50.10:8001/api/v1/draw"
    method: POST
    content_type: "application/json"
    payload: >
      {
        "leon_present": {{ states('input_boolean.leon_present') == 'on' }},
        "emmi_present": {{ states('input_boolean.emmi_present') == 'on' }},
        "elsa_present": {{ states('input_boolean.elsa_present') == 'on' }},
        {% set ts = now().strftime('%Y%m%d%H%M%S%f') %}
        {% set flags = ('1' if states('input_boolean.leon_present') == 'on' else '0') ~ ('1' if states('input_boolean.emmi_present') == 'on' else '0') ~ ('1' if states('input_boolean.elsa_present') == 'on' else '0') %}
        {% set raw = (ts ~ flags ~ '000000000000000000000000000000')[:32] %}
        "request_id": "{{ raw[0:8] }}-{{ raw[8:12] }}-{{ raw[12:16] }}-{{ raw[16:20] }}-{{ raw[20:32] }}"
      }
```

Hinweis: Der Controller akzeptiert pro Tag genau einen effektiven Draw. Wiederholte
Läufe desselben Tages werden deshalb über den bereits gespeicherten effektiven Draw
aufgelöst.

Für Home Assistant ist zusätzlich sinnvoll, `generated_at`, `draw_id` und `date`
aus der API in eigene Anzeige-Helfer zu schreiben. So bleibt sichtbar, wann genau
der aktuell angezeigte Draw in der Datenbank persistiert wurde.

Optional kann der Controller einen lokalen Router beobachten. Wenn `router_enabled`
nicht gesetzt ist oder `router_url` fehlt, läuft der Kernpfad ohne Router weiter.
Die Router-Antwort darf nur eine supervisorische Bewertung liefern, keine
neue Reihenfolge oder DB-Anweisung.

## Admin-Oberflaeche

Die Betriebsoberflaeche laeuft als Vue-3-SPA unter:

- `GET /admin`
- `GET /admin/draws`
- `GET /admin/windows`
- `GET /admin/config`

Die SPA spricht dieselbe Admin-JSON-API an:

- `GET /admin/api/v1/overview`
- `POST /admin/api/v1/actions/draw`
- `POST /admin/api/v1/actions/router-probe`
- `POST /admin/api/v1/actions/backup`

Die Admin-UI sendet bei Draw-Aktionen nur Anwesenheit plus `request_id`.
Ein separater Modus wird nicht im Request übertragen. Der finale Modus wird
immer serverseitig aus der Anwesenheit abgeleitet und im Response zurückgegeben.

---

## Modus-Logik (Übersicht)

| Anwesend | Modus | pos3 | window_index | perm_code | pair_key |
|---|---|---|---|---|---|
| alle drei | TRIPLET | gesetzt | gesetzt | gesetzt | NULL |
| zwei | PAIR | NULL | NULL | NULL | gesetzt |
| eines | SINGLE | NULL | NULL | NULL | NULL |
| niemand | SKIP | NULL | NULL | NULL | NULL |
