"""
tests/test_present_mask.py
Tests für present_mask-Bitmaskenlogik.

Pflichtprüfungen:
  1. present_mask ist nicht JSON
  2. window_status_enum enthält kein ABORTED
  3. request_id ist Pflichtfeld
"""
from __future__ import annotations

import pytest
from datetime import date
from uuid import UUID, uuid4

from core.models import (
    DrawRequest,
    DrawMode,
    MASK_LEON,
    MASK_EMMI,
    MASK_ELSA,
    MASK_ALL,
    WindowStatus,
)
from core.validation import validate_present_mask_is_smallint, ValidationError


# ---------------------------------------------------------------------------
# 1. present_mask ist nicht JSON (Pflichtprüfung)
# ---------------------------------------------------------------------------

class TestPresentMaskIsNotJson:
    def test_integer_value_is_accepted(self):
        """present_mask muss int sein."""
        validate_present_mask_is_smallint(7)  # kein Fehler

    def test_dict_raises_validation_error(self):
        """present_mask als dict muss ValidationError auslösen."""
        with pytest.raises(ValidationError) as exc_info:
            validate_present_mask_is_smallint({"leon": True, "emmi": True, "elsa": False})
        assert exc_info.value.field == "present_mask"
        assert "SMALLINT" in exc_info.value.message

    def test_list_raises_validation_error(self):
        """present_mask als Liste muss ValidationError auslösen."""
        with pytest.raises(ValidationError):
            validate_present_mask_is_smallint([1, 2, 3])

    def test_string_raises_validation_error(self):
        """present_mask als String muss ValidationError auslösen."""
        with pytest.raises(ValidationError):
            validate_present_mask_is_smallint("7")

    def test_none_raises_validation_error(self):
        """present_mask als None muss ValidationError auslösen."""
        with pytest.raises(ValidationError):
            validate_present_mask_is_smallint(None)


# ---------------------------------------------------------------------------
# Bitmasken-Arithmetik
# ---------------------------------------------------------------------------

class TestPresentMaskBitlogic:
    def _req(self, leon: bool, emmi: bool, elsa: bool) -> DrawRequest:
        return DrawRequest(
            request_id=uuid4(),
            leon_present=leon,
            emmi_present=emmi,
            elsa_present=elsa,
        )

    def test_mask_niemand(self):
        assert self._req(False, False, False).present_mask == 0

    def test_mask_nur_leon(self):
        assert self._req(True, False, False).present_mask == MASK_LEON  # 1

    def test_mask_nur_emmi(self):
        assert self._req(False, True, False).present_mask == MASK_EMMI  # 2

    def test_mask_nur_elsa(self):
        assert self._req(False, False, True).present_mask == MASK_ELSA  # 4

    def test_mask_leon_emmi(self):
        assert self._req(True, True, False).present_mask == 3

    def test_mask_leon_elsa(self):
        assert self._req(True, False, True).present_mask == 5

    def test_mask_emmi_elsa(self):
        assert self._req(False, True, True).present_mask == 6

    def test_mask_alle_drei(self):
        assert self._req(True, True, True).present_mask == MASK_ALL  # 7

    def test_mask_range_never_exceeds_7(self):
        for l in [True, False]:
            for e in [True, False]:
                for s in [True, False]:
                    mask = self._req(l, e, s).present_mask
                    assert 0 <= mask <= 7, f"Ungültige Maske: {mask}"

    def test_mask_type_is_int_not_dict(self):
        """Pflicht: present_mask ist int, niemals dict oder JSON."""
        req = self._req(True, True, True)
        assert isinstance(req.present_mask, int)
        assert not isinstance(req.present_mask, dict)
        assert not isinstance(req.present_mask, list)


# ---------------------------------------------------------------------------
# 2. window_status_enum enthält kein ABORTED (Pflichtprüfung)
# ---------------------------------------------------------------------------

class TestWindowStatusEnum:
    def test_only_active_and_completed(self):
        """window_status_enum darf nur ACTIVE und COMPLETED enthalten."""
        valid_values = {s.value for s in WindowStatus}
        assert valid_values == {"ACTIVE", "COMPLETED"}

    def test_aborted_does_not_exist(self):
        """ABORTED darf nicht als WindowStatus existieren."""
        assert "ABORTED" not in {s.value for s in WindowStatus}

    def test_aborted_raises_value_error(self):
        with pytest.raises(ValueError):
            WindowStatus("ABORTED")


# ---------------------------------------------------------------------------
# 3. request_id ist Pflichtfeld (Pflichtprüfung)
# ---------------------------------------------------------------------------

class TestRequestIdRequired:
    def test_request_id_is_uuid(self):
        """request_id muss UUID sein."""
        rid = uuid4()
        req = DrawRequest(
            request_id=rid,
            leon_present=True,
            emmi_present=False,
            elsa_present=False,
        )
        assert req.request_id == rid
        assert isinstance(req.request_id, UUID)

    def test_null_uuid_rejected_by_validation(self):
        """Null-UUID (int=0) muss von validate_draw_request abgelehnt werden."""
        from core.validation import validate_draw_request
        req = DrawRequest(
            request_id=UUID(int=0),
            leon_present=True,
            emmi_present=False,
            elsa_present=False,
        )
        with pytest.raises(ValidationError) as exc_info:
            validate_draw_request(req)
        assert exc_info.value.field == "request_id"

    def test_different_request_ids_produce_different_hashes(self):
        """Zwei verschiedene request_ids erzeugen verschiedene seed_hashes."""
        from core.algorithm import _compute_seed_hash
        rid1 = uuid4()
        rid2 = uuid4()
        h1 = _compute_seed_hash(rid1, date.today(), DrawMode.TRIPLET)
        h2 = _compute_seed_hash(rid2, date.today(), DrawMode.TRIPLET)
        assert h1 != h2

    def test_seed_hash_is_64_chars(self):
        """seed_material_hash muss genau 64 Zeichen (SHA-256 Hex) haben."""
        from core.algorithm import _compute_seed_hash
        h = _compute_seed_hash(uuid4(), date.today(), DrawMode.SINGLE)
        assert len(h) == 64
