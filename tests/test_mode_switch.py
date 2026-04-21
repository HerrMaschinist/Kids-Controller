"""
tests/test_mode_switch.py
Tests für Moduswechsel (TRIPLET/PAIR/SINGLE/SKIP) und Algorithmusverhalten.

Pflichtprüfung:
  4. draws.window_index ist nullable (nur bei TRIPLET gesetzt)
"""
from __future__ import annotations

from datetime import date
from uuid import uuid4

import pytest

from core.algorithm import build_draw_from_context, _shuffle_permutation_sequence
from core.models import (
    DrawContext,
    DrawMode,
    DrawRequest,
    FairnessWindow,
    derive_draw_mode_from_presence,
    PermCode,
    WindowStatus,
)


def _make_request(leon: bool, emmi: bool, elsa: bool) -> DrawRequest:
    return DrawRequest(
        request_id=uuid4(),
        leon_present=leon,
        emmi_present=emmi,
        elsa_present=elsa,
        draw_date=date(2025, 1, 15),
    )


def _make_active_window(index: int = 0) -> FairnessWindow:
    from datetime import datetime, timezone
    seq = _shuffle_permutation_sequence(seed=42)
    return FairnessWindow(
        id=1,
        window_id="ABCD1234",
        window_start_date=date(2025, 1, 1),
        window_status=WindowStatus.ACTIVE,
        window_index=index,
        window_size=12,
        permutation_sequence=seq,
        last_full_order=None,
        last_full_draw_date=None,
        last_mode=None,
        seed_material_hash="a" * 64,
        shuffle_algorithm="fisher_yates",
        algorithm_version="1.0.0",
        created_at=datetime.now(tz=timezone.utc),
        updated_at=datetime.now(tz=timezone.utc),
    )


def _make_context(
    request: DrawRequest,
    active_window: FairnessWindow | None = None,
) -> DrawContext:
    return DrawContext.from_request(request, active_window)


# ---------------------------------------------------------------------------
# Moduserkennung aus present_mask
# ---------------------------------------------------------------------------

class TestModeDetection:
    def test_triplet_all_present(self):
        req = _make_request(True, True, True)
        assert req.determine_mode() == DrawMode.TRIPLET

    def test_pair_two_present(self):
        req = _make_request(True, True, False)
        assert req.determine_mode() == DrawMode.PAIR

    def test_single_one_present(self):
        req = _make_request(True, False, False)
        assert req.determine_mode() == DrawMode.SINGLE

    def test_skip_none_present(self):
        req = _make_request(False, False, False)
        assert req.determine_mode() == DrawMode.SKIP

    def test_central_derive_function_matches_matrix(self):
        assert derive_draw_mode_from_presence(True, True, True) == DrawMode.TRIPLET
        assert derive_draw_mode_from_presence(True, True, False) == DrawMode.PAIR
        assert derive_draw_mode_from_presence(True, False, False) == DrawMode.SINGLE
        assert derive_draw_mode_from_presence(False, False, False) == DrawMode.SKIP

    def test_central_derive_function_handles_unexpected_values_gracefully(self):
        assert derive_draw_mode_from_presence(None, -1, "yes") == DrawMode.SKIP
        assert derive_draw_mode_from_presence(True, object(), False) == DrawMode.SINGLE

    def test_mode_does_not_stick_across_changes(self):
        req = _make_request(True, True, True)
        assert req.determine_mode() == DrawMode.TRIPLET

        req = _make_request(True, True, False)
        assert req.determine_mode() == DrawMode.PAIR

        req = _make_request(True, False, False)
        assert req.determine_mode() == DrawMode.SINGLE

        req = _make_request(False, False, False)
        assert req.determine_mode() == DrawMode.SKIP

        req = _make_request(False, True, False)
        assert req.determine_mode() == DrawMode.SINGLE


# ---------------------------------------------------------------------------
# SKIP
# ---------------------------------------------------------------------------

class TestSkipMode:
    def test_skip_all_positions_null(self):
        req = _make_request(False, False, False)
        draw, updated_window = build_draw_from_context(_make_context(req))
        assert draw.mode == DrawMode.SKIP
        assert draw.pos1 is None
        assert draw.pos2 is None
        assert draw.pos3 is None
        assert draw.stop_morning is None
        assert draw.stop_midday is None

    def test_skip_window_index_is_none(self):
        """Pflichtprüfung 4: window_index ist bei SKIP NULL."""
        req = _make_request(False, False, False)
        draw, _ = build_draw_from_context(_make_context(req))
        assert draw.window_index is None

    def test_skip_no_window_update(self):
        req = _make_request(False, False, False)
        _, updated_window = build_draw_from_context(_make_context(req))
        assert updated_window is None


# ---------------------------------------------------------------------------
# SINGLE
# ---------------------------------------------------------------------------

class TestSingleMode:
    def test_single_leon(self):
        req = _make_request(True, False, False)
        draw, _ = build_draw_from_context(_make_context(req))
        assert draw.mode == DrawMode.SINGLE
        assert draw.pos1 == 1  # Leon
        assert draw.pos2 is None
        assert draw.pos3 is None
        assert draw.stop_morning == 1
        assert draw.stop_midday == 1

    def test_single_emmi(self):
        req = _make_request(False, True, False)
        draw, _ = build_draw_from_context(_make_context(req))
        assert draw.pos1 == 2  # Emmi

    def test_single_elsa(self):
        req = _make_request(False, False, True)
        draw, _ = build_draw_from_context(_make_context(req))
        assert draw.pos1 == 3  # Elsa

    def test_single_window_index_is_none(self):
        """Pflichtprüfung 4: window_index ist bei SINGLE NULL."""
        req = _make_request(True, False, False)
        draw, _ = build_draw_from_context(_make_context(req))
        assert draw.window_index is None

    def test_single_perm_code_is_none(self):
        req = _make_request(False, True, False)
        draw, _ = build_draw_from_context(_make_context(req))
        assert draw.perm_code is None


# ---------------------------------------------------------------------------
# PAIR
# ---------------------------------------------------------------------------

class TestPairMode:
    def test_pair_pos3_is_none(self):
        req = _make_request(True, True, False)
        draw, _ = build_draw_from_context(_make_context(req))
        assert draw.mode == DrawMode.PAIR
        assert draw.pos3 is None

    def test_pair_window_index_is_none(self):
        """Pflichtprüfung 4: window_index ist bei PAIR NULL."""
        req = _make_request(True, True, False)
        draw, _ = build_draw_from_context(_make_context(req))
        assert draw.window_index is None

    def test_pair_perm_code_is_none(self):
        req = _make_request(True, False, True)
        draw, _ = build_draw_from_context(_make_context(req))
        assert draw.perm_code is None

    def test_pair_pair_key_set(self):
        req = _make_request(True, True, False)
        draw, _ = build_draw_from_context(_make_context(req))
        assert draw.pair_key is not None
        assert draw.pair_key.value == "12"

    def test_pair_cycle_index_is_int(self):
        req = _make_request(False, True, True)
        draw, _ = build_draw_from_context(_make_context(req))
        assert draw.pair_cycle_index in (0, 1)

    def test_pair_no_window_update(self):
        req = _make_request(True, True, False)
        _, updated_window = build_draw_from_context(_make_context(req))
        assert updated_window is None


# ---------------------------------------------------------------------------
# TRIPLET
# ---------------------------------------------------------------------------

class TestTripletMode:
    def test_triplet_new_window_created(self):
        req = _make_request(True, True, True)
        draw, updated_window = build_draw_from_context(_make_context(req))
        assert draw.mode == DrawMode.TRIPLET
        assert updated_window is not None

    def test_triplet_window_index_set(self):
        """Pflichtprüfung 4: window_index ist bei TRIPLET gesetzt (nicht NULL)."""
        req = _make_request(True, True, True)
        draw, _ = build_draw_from_context(_make_context(req))
        assert draw.window_index is not None
        assert isinstance(draw.window_index, int)

    def test_triplet_perm_code_set(self):
        req = _make_request(True, True, True)
        draw, _ = build_draw_from_context(_make_context(req))
        assert draw.perm_code is not None
        assert isinstance(draw.perm_code, PermCode)

    def test_triplet_pos1_pos2_pos3_all_set(self):
        req = _make_request(True, True, True)
        draw, _ = build_draw_from_context(_make_context(req))
        assert draw.pos1 in (1, 2, 3)
        assert draw.pos2 in (1, 2, 3)
        assert draw.pos3 in (1, 2, 3)

    def test_triplet_positions_are_distinct(self):
        req = _make_request(True, True, True)
        draw, _ = build_draw_from_context(_make_context(req))
        positions = [draw.pos1, draw.pos2, draw.pos3]
        assert len(set(positions)) == 3

    def test_triplet_window_index_advances(self):
        window = _make_active_window(index=5)
        req = _make_request(True, True, True)
        draw, updated_window = build_draw_from_context(_make_context(req, window))
        assert draw.window_index == 5
        assert updated_window.window_index == 6

    def test_triplet_window_completes_at_12(self):
        window = _make_active_window(index=11)
        req = _make_request(True, True, True)
        _, updated_window = build_draw_from_context(_make_context(req, window))
        assert updated_window.window_status == WindowStatus.COMPLETED
        assert updated_window.window_index == 12

    def test_triplet_continues_existing_window(self):
        """Rückkehrregel: bestehendes Fenster wird fortgesetzt."""
        window = _make_active_window(index=3)
        req = _make_request(True, True, True)
        draw, updated_window = build_draw_from_context(_make_context(req, window))
        assert draw.window_id == window.window_id
        assert updated_window.window_index == 4

    def test_triplet_new_window_is_deterministic_for_fixed_seed_material(self, monkeypatch):
        from core import algorithm

        monkeypatch.setattr(algorithm, "_generate_window_id", lambda: "ABCD1234")
        req = _make_request(True, True, True)

        _, window_one = build_draw_from_context(_make_context(req))
        _, window_two = build_draw_from_context(_make_context(req))

        assert window_one.permutation_sequence == window_two.permutation_sequence

    def test_triplet_replay_context_hash_is_deterministic(self):
        req = _make_request(True, True, True)

        draw_one, _ = build_draw_from_context(_make_context(req))
        draw_two, _ = build_draw_from_context(_make_context(req))

        assert len(draw_one.replay_context_hash) == 64
        assert draw_one.replay_context_hash == draw_two.replay_context_hash

    def test_permutation_sequence_has_12_entries(self):
        seq = _shuffle_permutation_sequence(seed=0)
        assert len(seq) == 12

    def test_permutation_sequence_each_perm_twice(self):
        from collections import Counter
        seq = _shuffle_permutation_sequence(seed=0)
        counts = Counter(seq)
        assert set(counts.keys()) == {"123", "132", "213", "231", "312", "321"}
        assert all(v == 2 for v in counts.values())

    def test_window_id_is_8_chars(self):
        from core.algorithm import _generate_window_id
        wid = _generate_window_id()
        assert len(wid) == 8
        assert wid.isalnum()
