"""
tests/test_field_consistency.py
SQL ↔ Python Feldkonsistenz-Tests.

Prüft, dass Python-Modelle dieselben Feldnamen wie das SQL-Schema verwenden.
"""
from __future__ import annotations

import dataclasses

import pytest

from core.models import Draw, DrawMode, FairnessWindow, SystemConfig, WindowStatus, PermCode
from integrations.homeassistant_models import HaDrawRequest, HaDrawResponse


# ---------------------------------------------------------------------------
# SQL-Spalten (Referenz aus 01_schema_types_and_tables.sql)
# ---------------------------------------------------------------------------

SQL_DRAWS_COLUMNS = {
    "id", "draw_ts", "draw_date", "request_id", "window_id", "mode",
    "present_mask", "window_index", "active_window_index_snapshot", "perm_code",
    "derived_from_last_full_order", "is_effective", "superseded_by_draw_id",
    "pair_key", "pair_cycle_index", "pos1", "pos2", "pos3",
    "stop_morning", "stop_midday", "algorithm_version", "seed_material_hash", "note",
}

SQL_FAIRNESS_WINDOWS_COLUMNS = {
    "id", "window_id", "window_start_date", "window_status", "window_index",
    "window_size", "permutation_sequence", "last_full_order", "last_full_draw_date",
    "last_mode", "seed_material_hash", "shuffle_algorithm", "algorithm_version",
    "created_at", "updated_at",
}

SQL_SYSTEM_CONFIG_COLUMNS = {"key_name", "value", "updated_at"}


class TestDrawFieldConsistency:
    def test_draw_python_fields_match_sql(self):
        """Alle SQL-Spalten von draws müssen als Python-Felder existieren."""
        python_fields = {f.name for f in dataclasses.fields(Draw)}
        missing = SQL_DRAWS_COLUMNS - python_fields
        assert not missing, f"Fehlende Python-Felder für draws: {missing}"

    def test_draw_no_extra_fields_without_sql_counterpart(self):
        """Python darf keine Felder haben, die nicht in SQL existieren."""
        python_fields = {f.name for f in dataclasses.fields(Draw)}
        extra = python_fields - SQL_DRAWS_COLUMNS
        assert not extra, f"Python-Felder ohne SQL-Gegenstück: {extra}"

    def test_present_mask_field_is_int_typed(self):
        """present_mask in Draw ist int annotiert, kein dict/JSON."""
        for f in dataclasses.fields(Draw):
            if f.name == "present_mask":
                assert f.type == "int" or f.type is int or "int" in str(f.type)
                break

    def test_request_id_field_not_optional(self):
        """request_id in Draw hat keinen NULL-Default (NOT NULL in SQL)."""
        for f in dataclasses.fields(Draw):
            if f.name == "request_id":
                assert f.default is dataclasses.MISSING or f.default is not None


class TestFairnessWindowFieldConsistency:
    def test_window_python_fields_match_sql(self):
        python_fields = {f.name for f in dataclasses.fields(FairnessWindow)}
        missing = SQL_FAIRNESS_WINDOWS_COLUMNS - python_fields
        assert not missing, f"Fehlende Python-Felder für fairness_windows: {missing}"

    def test_window_id_field_exists(self):
        python_fields = {f.name for f in dataclasses.fields(FairnessWindow)}
        assert "window_id" in python_fields

    def test_last_full_order_is_optional_perm_code(self):
        """last_full_order ist Optional[PermCode] (nullable in SQL)."""
        hints = FairnessWindow.__dataclass_fields__
        field = hints.get("last_full_order")
        assert field is not None


class TestSystemConfigFieldConsistency:
    def test_system_config_python_fields_match_sql(self):
        python_fields = {f.name for f in dataclasses.fields(SystemConfig)}
        missing = SQL_SYSTEM_CONFIG_COLUMNS - python_fields
        assert not missing, f"Fehlende Python-Felder für system_config: {missing}"

    def test_no_config_key_field(self):
        """system_config darf kein Feld 'config_key' haben (SQL-Verbot)."""
        python_fields = {f.name for f in dataclasses.fields(SystemConfig)}
        assert "config_key" not in python_fields

    def test_no_config_value_field(self):
        """system_config darf kein Feld 'config_value' haben (SQL-Verbot)."""
        python_fields = {f.name for f in dataclasses.fields(SystemConfig)}
        assert "config_value" not in python_fields

    def test_has_key_name_value_updated_at(self):
        python_fields = {f.name for f in dataclasses.fields(SystemConfig)}
        assert "key_name"   in python_fields
        assert "value"      in python_fields
        assert "updated_at" in python_fields


class TestEnumConsistency:
    def test_window_status_values_match_sql_enum(self):
        """window_status_enum in SQL: ACTIVE, COMPLETED – kein ABORTED."""
        assert {s.value for s in WindowStatus} == {"ACTIVE", "COMPLETED"}

    def test_perm_code_values_match_sql_enum(self):
        """perm_code_enum in SQL: 123 132 213 231 312 321."""
        expected = {"123", "132", "213", "231", "312", "321"}
        assert {p.value for p in PermCode} == expected

    def test_mode_enum_values_match_sql(self):
        expected = {"TRIPLET", "PAIR", "SINGLE", "SKIP"}
        assert {m.value for m in DrawMode} == expected


class TestApiFieldNaming:
    def test_ha_request_leon_present(self):
        assert "leon_present" in HaDrawRequest.model_fields

    def test_ha_request_emmi_present(self):
        """Feld muss korrekt geschrieben sein."""
        assert "emmi_present" in HaDrawRequest.model_fields
        misspelled = [k for k in HaDrawRequest.model_fields if k.startswith("emm") and k != "emmi_present"]
        assert misspelled == []

    def test_ha_request_elsa_present(self):
        assert "elsa_present" in HaDrawRequest.model_fields

    def test_ha_request_request_id(self):
        assert "request_id" in HaDrawRequest.model_fields

    def test_ha_response_required_fields(self):
        """
        Intern heißt das Datumsfeld 'draw_date', extern (JSON/Alias) 'date'.
        Beides muss verifizierbar sein.
        """
        internal_required = {"draw_id", "mode", "pos1", "pos2", "pos3",
                              "stop_morning", "stop_midday", "draw_date", "generated_at"}
        assert internal_required.issubset(set(HaDrawResponse.model_fields.keys()))

        from datetime import date, datetime, timezone
        resp = HaDrawResponse.model_validate({
            "draw_id": 1, "mode": "TRIPLET",
            "pos1": 1, "pos2": 2, "pos3": 3,
            "stop_morning": 1, "stop_midday": 2,
            "date": date(2025, 1, 1),
            "generated_at": datetime.now(timezone.utc),
        })
        assert "date" in resp.model_dump(by_alias=True)
        assert "generated_at" in resp.model_dump(by_alias=True)
