"""
tests/test_api_model_consistency.py
Tests für API-Modellkonsistenz.

Pflichtprüfung:
  3. request_id ist Pflichtfeld
  5. Der Name Emmi wird korrekt verwendet (Feldname: emmi_present)
"""
from __future__ import annotations

from datetime import date
from uuid import UUID, uuid4

import pytest
from pydantic import ValidationError as PydanticValidationError

from integrations.homeassistant_models import HaDrawRequest, HaDrawResponse
from integrations.homeassistant_adapter import (
    ha_request_to_domain,
    domain_draw_to_ha_response,
)
from core.models import Draw, DrawMode, PermCode, PairKey


# ---------------------------------------------------------------------------
# 5. Name Emmi wird korrekt verwendet (Pflichtprüfung)
# ---------------------------------------------------------------------------

class TestEmmiFieldNaming:
    def test_ha_request_has_emmi_present(self):
        """Das API-Feld heißt emmi_present."""
        model_fields = HaDrawRequest.model_fields
        assert "emmi_present" in model_fields

    def test_ha_request_no_incorrect_spelling(self):
        """Es darf keine falsch geschriebene Feldvariante existieren."""
        model_fields = HaDrawRequest.model_fields
        incorrect_variants = [k for k in model_fields if k.startswith("emm") and k != "emmi_present"]
        assert incorrect_variants == []

    def test_emmi_present_field_is_bool(self):
        """emmi_present muss bool sein."""
        field = HaDrawRequest.model_fields["emmi_present"]
        assert field.annotation is bool

    def test_ha_request_accepts_emmi_present(self):
        """HaDrawRequest akzeptiert emmi_present ohne Fehler."""
        req = HaDrawRequest(
            leon_present=False,
            emmi_present=True,
            elsa_present=False,
            request_id=uuid4(),
        )
        assert req.emmi_present is True

    def test_ha_request_all_three_field_names(self):
        """Alle drei Anwesenheitsfelder müssen exakt so heißen."""
        fields = set(HaDrawRequest.model_fields.keys())
        assert "leon_present" in fields
        assert "emmi_present" in fields
        assert "elsa_present" in fields
        assert "mode" not in fields

    def test_domain_request_has_emmi_present(self):
        """DrawRequest hat das korrekt geschriebene Anwesenheitsfeld."""
        from core.models import DrawRequest
        import dataclasses
        field_names = {f.name for f in dataclasses.fields(DrawRequest)}
        assert "emmi_present" in field_names
        misspelled = [n for n in field_names if n.startswith("emm") and n != "emmi_present"]
        assert misspelled == []

    def test_kids_dict_uses_correct_name(self):
        """KIDS-Konstante verwendet den korrekten Namen für Kind 2."""
        from core.models import KIDS, EMMI_ID
        assert KIDS[EMMI_ID] == "Emmi"


# ---------------------------------------------------------------------------
# 3. request_id ist Pflichtfeld (Pflichtprüfung in API-Schicht)
# ---------------------------------------------------------------------------

class TestRequestIdRequired:
    def test_request_id_required_in_ha_request(self):
        """request_id fehlt → PydanticValidationError."""
        with pytest.raises(PydanticValidationError) as exc_info:
            HaDrawRequest(
                leon_present=True,
                emmi_present=False,
                elsa_present=False,
                # request_id fehlt absichtlich
            )
        errors = exc_info.value.errors()
        field_names = [e["loc"][0] for e in errors]
        assert "request_id" in field_names

    def test_request_id_must_be_uuid(self):
        """request_id muss eine gültige UUID sein."""
        with pytest.raises(PydanticValidationError):
            HaDrawRequest(
                leon_present=True,
                emmi_present=False,
                elsa_present=False,
                request_id="kein-uuid",
            )

    def test_valid_request_id_accepted(self):
        rid = uuid4()
        req = HaDrawRequest(
            leon_present=True,
            emmi_present=True,
            elsa_present=True,
            request_id=rid,
        )
        assert req.request_id == rid


# ---------------------------------------------------------------------------
# Adapter: HaDrawRequest → DrawRequest
# ---------------------------------------------------------------------------

class TestHaAdapter:
    def _make_ha_request(self, leon: bool = True, emmi: bool = True, elsa: bool = True) -> HaDrawRequest:
        return HaDrawRequest(
            leon_present=leon,
            emmi_present=emmi,
            elsa_present=elsa,
            request_id=uuid4(),
        )

    def test_adapter_maps_emmi_present(self):
        ha_req = self._make_ha_request(leon=False, emmi=True, elsa=False)
        domain_req = ha_request_to_domain(ha_req)
        assert domain_req.emmi_present is True
        assert domain_req.leon_present is False
        assert domain_req.elsa_present is False

    def test_adapter_maps_request_id(self):
        ha_req = self._make_ha_request()
        domain_req = ha_request_to_domain(ha_req)
        assert domain_req.request_id == ha_req.request_id

    def test_adapter_sets_draw_date(self):
        ha_req = self._make_ha_request()
        today = date.today()
        domain_req = ha_request_to_domain(ha_req, draw_date=today)
        assert domain_req.draw_date == today

    def test_domain_to_ha_response_maps_all_fields(self):
        from datetime import datetime, timezone
        draw = Draw(
            id=99,
            draw_ts=datetime.now(tz=timezone.utc),
            draw_date=date.today(),
            request_id=uuid4(),
            window_id="WXYZ5678",
            mode=DrawMode.TRIPLET,
            present_mask=7,
            window_index=4,
            active_window_index_snapshot=4,
            perm_code=PermCode.P312,
            derived_from_last_full_order=False,
            is_effective=True,
            superseded_by_draw_id=None,
            pair_key=None,
            pair_cycle_index=None,
            pos1=3,
            pos2=1,
            pos3=2,
            stop_morning=3,
            stop_midday=1,
            algorithm_version="1.0.0",
            seed_material_hash="c" * 64,
            replay_context_hash="d" * 64,
            note=None,
        )
        resp = domain_draw_to_ha_response(draw)
        assert resp.draw_id == 99
        assert resp.mode == "TRIPLET"
        assert resp.pos1 == 3
        assert resp.pos2 == 1
        assert resp.pos3 == 2
        assert resp.stop_morning == 3
        assert resp.stop_midday == 1
        assert resp.draw_date == date.today()
        # Alias-Prüfung: serialisiert als "date"
        serialized = resp.model_dump(by_alias=True)
        assert "date" in serialized
        assert serialized["date"] == date.today()

    def test_request_has_no_mode_field(self):
        ha_req = self._make_ha_request()
        domain_req = ha_request_to_domain(ha_req)
        assert domain_req.determine_mode() == DrawMode.TRIPLET
        assert not hasattr(ha_req, "mode")

    def test_ha_response_has_required_fields(self):
        """
        HaDrawResponse muss alle Pflichtfelder enthalten.
        Das Datumsfeld heißt intern 'draw_date', wird aber als 'date' serialisiert (Alias).
        """
        internal_required = {"draw_id", "mode", "pos1", "pos2", "pos3",
                             "stop_morning", "stop_midday", "draw_date", "generated_at"}
        response_fields = set(HaDrawResponse.model_fields.keys())
        assert internal_required.issubset(response_fields)

        from datetime import date, datetime, timezone
        resp = HaDrawResponse.model_validate({
            "draw_id": 1, "mode": "SKIP",
            "pos1": None, "pos2": None, "pos3": None,
            "stop_morning": None, "stop_midday": None,
            "date": date.today(),
            "generated_at": datetime.now(timezone.utc),
        })
        serialized = resp.model_dump(by_alias=True)
        assert "date" in serialized
        assert "draw_date" not in serialized
        assert "generated_at" in serialized
