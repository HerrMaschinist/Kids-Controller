# KIDS_CONTROLLER – Test Report

## Ergebnis

```
116 passed, 0 failed, 0 warning
```

---

## Testdateien

### tests/test_present_mask.py

Prüft die Bitmaskenlogik und Pflichtbedingungen.

| Testklasse | Beschreibung |
|---|---|
| `TestPresentMaskIsNotJson` | present_mask muss int sein – dict, list, str, None lösen ValidationError aus |
| `TestPresentMaskBitlogic` | Alle 8 Maskenwerte (0–7) korrekt; Typ ist int, kein dict |
| `TestWindowStatusEnum` | Nur ACTIVE und COMPLETED; ABORTED löst ValueError aus |
| `TestRequestIdRequired` | request_id ist UUID; Null-UUID wird abgelehnt; Hashes sind 64 Zeichen |

### tests/test_mode_switch.py

Prüft Moduserkennung, Algorithmusverhalten und Fenster-Logik.

| Testklasse | Beschreibung |
|---|---|
| `TestModeDetection` | TRIPLET/PAIR/SINGLE/SKIP aus Anwesenheit |
| `TestSkipMode` | Alle Positionen NULL; window_index NULL |
| `TestSingleMode` | pos1 = Kind-ID; pos2/pos3 NULL; window_index NULL |
| `TestPairMode` | pos3 NULL; window_index NULL; perm_code NULL; pair_key gesetzt |
| `TestTripletMode` | Fenster-Logik; window_index gesetzt; 12er-Sequenz; Permutationen distinct |

### tests/test_repository_interfaces.py

Prüft Mapper-Logik ohne Datenbankverbindung.

| Testklasse | Beschreibung |
|---|---|
| `TestDrawToInsertParams` | present_mask int; mode als String; window_index NULL für PAIR |
| `TestWindowMappers` | window_id 8 Zeichen; permutation_sequence als JSON-String |

### tests/test_api_model_consistency.py

Prüft API-Modelle und Adapter.

| Testklasse | Beschreibung |
|---|---|
| `TestEmmiFieldNaming` | Feld heißt korrekt `emmi_present`; KIDS-Konstante = "Emmi" |
| `TestRequestIdRequired` | request_id Pflichtfeld; ungültige UUID wird abgelehnt |
| `TestHaAdapter` | Adapter-Mapping; `date`-Alias in serialisierter Antwort |

### tests/test_field_consistency.py

Prüft SQL ↔ Python Feldkonsistenz.

| Testklasse | Beschreibung |
|---|---|
| `TestDrawFieldConsistency` | Alle SQL-Spalten von draws als Python-Felder vorhanden |
| `TestFairnessWindowFieldConsistency` | Alle SQL-Spalten von fairness_windows als Python-Felder |
| `TestSystemConfigFieldConsistency` | key_name/value/updated_at; kein config_key/config_value |
| `TestEnumConsistency` | WindowStatus/PermCode/DrawMode stimmen mit SQL-ENUMs überein |
| `TestApiFieldNaming` | leon_present/emmi_present/elsa_present/request_id; date-Alias |

### tests/test_draw_service.py

Prüft den produktiven Draw-Pfad auf Service-Ebene.

| Testklasse | Beschreibung |
|---|---|
| `test_triplet_full_window_advances_to_completed` | 12er-TRIPLET-Fenster läuft sauber bis COMPLETED |
| `test_pair_sequence_rotates_and_uses_last_full_order` | PAIR alterniert korrekt und nutzt last_full_order |
| `test_single_and_skip_outputs` | SINGLE und SKIP setzen nur die erwarteten Felder |
| `test_missing_active_window_creates_new_window_before_draw` | Recovery ohne aktives Fenster |
| `test_duplicate_request_id_returns_existing_draw_without_persisting` | Idempotenz bei Doppelaufruf |
| `test_uq_active_window_conflict_retries_once` | Retry bei aktivem Fensterkonflikt |
| `test_uq_effective_draw_per_date_returns_existing_draw` | Wiederholung am selben Tag liefert bestehenden effektiven Draw |

### tests/test_router_supervisor.py

Prüft Router-Client und Statusschicht.

| Testklasse | Beschreibung |
|---|---|
| `test_router_client_disabled_is_non_blocking` | Router aus = Kern läuft weiter |
| `test_router_client_parses_assessment` | Router-Antwort wird strukturiert geparst |
| `test_router_timeout_degrades_without_changing_core` | Timeout degradiert nur Router-Pfad |
| `test_router_invalid_json_degrades` | Ungültiges JSON degradiert nur Router-Pfad |
| `test_router_wrong_structure_degrades` | Formell falsche Struktur wird abgelehnt |
| `test_supervisor_snapshot_reports_status` | Status-Snapshot aus DB + Laufzeitstatus |
| `test_status_reflects_router_configuration_before_probe` | Router-Aktivierung wird auch ohne Probe im Status angezeigt |
| `test_status_reflects_router_error_after_probe` | Routerfehler erscheint im Statuspfad |
| `test_router_failure_keeps_last_valid_assessment` | Letzte valide Router-Bewertung bleibt nach Fehler erhalten |

Routerpfad:
- `/route`
- Authentifizierung über `X-API-Key`
- Router-Ausfall degradiert nur den Routerpfad, nicht den Kern

---

## Pflichtprüfungen (aus Auftrag Abschnitt 12)

| # | Prüfung | Test | Ergebnis |
|---|---|---|---|
| 1 | `present_mask` ist nicht JSON | `TestPresentMaskIsNotJson::test_dict_raises_validation_error` | PASSED |
| 2 | `window_status_enum` enthält kein `ABORTED` | `TestWindowStatusEnum::test_aborted_does_not_exist` | PASSED |
| 3 | `request_id` ist Pflichtfeld | `TestRequestIdRequired::test_request_id_required_in_ha_request` | PASSED |
| 4 | `draws.window_index` ist nullable | `TestSkipMode::test_skip_window_index_is_none`, `TestSingleMode::test_single_window_index_is_none`, `TestPairMode::test_pair_window_index_is_none` | PASSED |
| 5 | Name `Emmi` wird korrekt verwendet | `TestEmmiFieldNaming::test_kids_dict_uses_emmi`, `TestApiFieldNaming::test_ha_request_emmi_present_not_emmy` | PASSED |

---

## Alias-Entscheidung `date`

Das Antwortfeld `date` der API (Abschnitt 8.3 des Auftrags) kollidiert in Pydantic v2
mit dem internen Typnamen `date`. Die Lösung: internes Feld `draw_date`, Pydantic-Alias `"date"`.

Abgedeckt durch:
- `TestHaAdapter::test_domain_to_ha_response_maps_all_fields` – prüft `resp.draw_date` und `serialized["date"]`
- `TestHaAdapter::test_ha_response_has_required_fields` – prüft interne Felder und Alias-Serialisierung
- `TestApiFieldNaming::test_ha_response_required_fields` – prüft interne Felder und Alias

---

## Testausführung

```bash
cd /opt/kids_controller
python -m pytest tests/ -v
```

Erwartet: `116 passed`.
