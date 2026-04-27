"""
tests/test_repository_interfaces.py
Tests für Repository-Schnittstellen ohne echte Datenbankverbindung.
Prüft Mapper-Logik und Parameterstruktur.
"""
from __future__ import annotations

from datetime import date, datetime, timedelta, timezone
from uuid import uuid4

import pytest

from core.models import (
    Draw,
    DrawMode,
    FairnessWindow,
    PairKey,
    PermCode,
    WindowStatus,
)
from persistence.mappers import (
    draw_to_insert_params,
    window_to_insert_params,
    window_to_update_params,
)


def _make_draw(mode: DrawMode = DrawMode.TRIPLET) -> Draw:
    return Draw(
        id=0,
        draw_ts=datetime.now(tz=timezone.utc),
        draw_date=date.today(),
        request_id=uuid4(),
        window_id="ABCD1234",
        mode=mode,
        present_mask=7,
        window_index=3 if mode == DrawMode.TRIPLET else None,
        active_window_index_snapshot=3 if mode == DrawMode.TRIPLET else None,
        perm_code=PermCode.P123 if mode == DrawMode.TRIPLET else None,
        derived_from_last_full_order=False,
        is_effective=True,
        superseded_by_draw_id=None,
        pair_key=None,
        pair_cycle_index=None,
        pos1=1,
        pos2=2,
        pos3=3 if mode == DrawMode.TRIPLET else None,
        stop_morning=1,
        stop_midday=2,
        algorithm_version="1.0.0",
        seed_material_hash="a" * 64,
        replay_context_hash="r" * 64,
        note=None,
    )


def _make_window() -> FairnessWindow:
    return FairnessWindow(
        id=1,
        window_id="ABCD1234",
        window_start_date=date.today() - timedelta(days=1),
        window_status=WindowStatus.ACTIVE,
        window_index=3,
        window_size=12,
        permutation_sequence=["123", "132", "213", "231", "312", "321",
                               "123", "132", "213", "231", "312", "321"],
        last_full_order=PermCode.P231,
        last_full_draw_date=date.today() - timedelta(days=1),
        last_mode=DrawMode.TRIPLET,
        seed_material_hash="b" * 64,
        shuffle_algorithm="fisher_yates",
        algorithm_version="1.0.0",
        created_at=datetime.now(tz=timezone.utc),
        updated_at=datetime.now(tz=timezone.utc),
    )


class TestDrawToInsertParams:
    def test_present_mask_is_int(self):
        """present_mask muss im Insert-Dict ein int sein, kein JSON."""
        draw = _make_draw()
        params = draw_to_insert_params(draw)
        assert isinstance(params["present_mask"], int)
        assert not isinstance(params["present_mask"], dict)

    def test_mode_is_string_value(self):
        draw = _make_draw()
        params = draw_to_insert_params(draw)
        assert params["mode"] == "TRIPLET"

    def test_perm_code_is_string_or_none(self):
        draw = _make_draw(DrawMode.TRIPLET)
        params = draw_to_insert_params(draw)
        assert params["perm_code"] == "123"

    def test_perm_code_none_for_pair(self):
        draw = _make_draw(DrawMode.PAIR)
        params = draw_to_insert_params(draw)
        assert params["perm_code"] is None

    def test_window_index_none_for_pair(self):
        """window_index muss für PAIR None sein."""
        draw = _make_draw(DrawMode.PAIR)
        params = draw_to_insert_params(draw)
        assert params["window_index"] is None

    def test_request_id_is_string(self):
        draw = _make_draw()
        params = draw_to_insert_params(draw)
        assert isinstance(params["request_id"], str)

    def test_all_required_keys_present(self):
        required = {
            "draw_ts", "draw_date", "request_id", "window_id", "mode",
            "present_mask", "window_index", "active_window_index_snapshot",
            "perm_code", "derived_from_last_full_order", "is_effective",
            "superseded_by_draw_id", "pair_key", "pair_cycle_index",
            "pos1", "pos2", "pos3", "stop_morning", "stop_midday",
            "algorithm_version", "seed_material_hash", "replay_context_hash",
            "note",
        }
        params = draw_to_insert_params(_make_draw())
        assert required.issubset(params.keys())

    def test_replay_context_hash_is_string(self):
        draw = _make_draw()
        params = draw_to_insert_params(draw)
        assert isinstance(params["replay_context_hash"], str)
        assert len(params["replay_context_hash"]) == 64


class TestWindowMappers:
    def test_insert_params_has_window_id(self):
        window = _make_window()
        params = window_to_insert_params(window)
        assert params["window_id"] == "ABCD1234"
        assert len(params["window_id"]) == 8

    def test_insert_params_permutation_sequence_is_json_string(self):
        import json
        window = _make_window()
        params = window_to_insert_params(window)
        seq = json.loads(params["permutation_sequence"])
        assert isinstance(seq, list)
        assert len(seq) == 12

    def test_insert_params_last_full_order_as_string(self):
        window = _make_window()
        params = window_to_insert_params(window)
        assert params["last_full_order"] == "231"

    def test_update_params_has_id(self):
        window = _make_window()
        params = window_to_update_params(window)
        assert params["id"] == 1

    def test_update_params_window_status_string(self):
        window = _make_window()
        params = window_to_update_params(window)
        assert params["window_status"] == "ACTIVE"

    def test_window_id_length_8(self):
        window = _make_window()
        assert len(window.window_id) == 8
