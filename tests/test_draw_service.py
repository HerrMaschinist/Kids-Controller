"""
tests/test_draw_service.py
Service-Tests für den produktiven Draw-Pfad.

Ziel: TRIPLET/PAIR/SINGLE/SKIP, Fensterwechsel, Idempotenz und Konfliktpfade
über die reale DrawService-Orchestrierung absichern, ohne die produktive DB zu
verändern.
"""
from __future__ import annotations

import asyncio
from dataclasses import replace
from datetime import date, datetime, timezone
from types import SimpleNamespace
from uuid import uuid4

import pytest

from core.algorithm import _shuffle_permutation_sequence
from core.draw_service import DrawService
from core.models import (
    Draw,
    DrawMode,
    DrawRequest,
    FairnessWindow,
    PermCode,
    WindowStatus,
)


class FakeUniqueViolation(Exception):
    def __init__(self, constraint_name: str) -> None:
        super().__init__(constraint_name)
        self.diag = SimpleNamespace(constraint_name=constraint_name)


class _FakeTransaction:
    async def __aenter__(self):
        return object()

    async def __aexit__(self, exc_type, exc, tb):
        return False


class FakeWindowRepo:
    def __init__(self, active_window: FairnessWindow | None) -> None:
        self.active_window = active_window
        self.insert_calls = 0
        self.update_calls = 0
        self.fail_first_insert_constraint: str | None = None
        self._failed_once = False

    def transaction(self):
        return _FakeTransaction()

    async def find_active_with_lock(self, conn):
        return self.active_window

    async def insert(self, window: FairnessWindow, conn):
        self.insert_calls += 1
        if self.fail_first_insert_constraint and not self._failed_once:
            self._failed_once = True
            raise FakeUniqueViolation(self.fail_first_insert_constraint)
        if window.id == 0:
            window = replace(window, id=1)
        self.active_window = window
        return window

    async def update(self, window: FairnessWindow, conn):
        self.update_calls += 1
        self.active_window = window
        return window


class FakeDrawRepo:
    def __init__(self) -> None:
        self.draws: list[Draw] = []
        self.insert_calls = 0
        self.fail_first_insert_constraint: str | None = None
        self._failed_once = False

    async def find_by_request_id(self, request_id):
        for draw in self.draws:
            if draw.request_id == request_id:
                return draw
        return None

    async def find_last_pair_for_key(self, pair_key, conn):
        for draw in reversed(self.draws):
            if draw.mode == DrawMode.PAIR and draw.pair_key == pair_key and draw.is_effective:
                return draw
        return None

    async def find_effective_by_date(self, draw_date):
        for draw in reversed(self.draws):
            if draw.draw_date == draw_date and draw.is_effective:
                return draw
        return None

    async def insert(self, draw: Draw, conn):
        self.insert_calls += 1
        if self.fail_first_insert_constraint and not self._failed_once:
            self._failed_once = True
            raise FakeUniqueViolation(self.fail_first_insert_constraint)
        self.draws.append(draw)
        return draw


def _make_active_window(index: int = 0, last_full_order: PermCode | None = None) -> FairnessWindow:
    now = datetime.now(tz=timezone.utc)
    return FairnessWindow(
        id=1,
        window_id="ABCD1234",
        window_start_date=date(2025, 1, 1),
        window_status=WindowStatus.ACTIVE,
        window_index=index,
        window_size=12,
        permutation_sequence=_shuffle_permutation_sequence(seed=42),
        last_full_order=last_full_order,
        last_full_draw_date=date(2025, 1, 1) if last_full_order else None,
        last_mode=DrawMode.TRIPLET if last_full_order else None,
        seed_material_hash="a" * 64,
        shuffle_algorithm="fisher_yates",
        algorithm_version="1.0.0",
        created_at=now,
        updated_at=now,
    )


def _make_request(leon: bool, emmi: bool, elsa: bool, *, request_id=None, draw_date=None) -> DrawRequest:
    return DrawRequest(
        request_id=request_id or uuid4(),
        leon_present=leon,
        emmi_present=emmi,
        elsa_present=elsa,
        draw_date=draw_date or date(2025, 1, 15),
    )


def _run(coro):
    return asyncio.run(coro)


def test_triplet_full_window_advances_to_completed():
    window_repo = FakeWindowRepo(_make_active_window(index=0))
    draw_repo = FakeDrawRepo()
    service = DrawService(window_repo, draw_repo)

    draws = []
    for _ in range(12):
        draw = _run(service.execute(_make_request(True, True, True)))
        draws.append(draw)
        window_repo.active_window = replace(window_repo.active_window, updated_at=datetime.now(tz=timezone.utc))

    assert [d.window_index for d in draws] == list(range(12))
    assert window_repo.active_window.window_status == WindowStatus.COMPLETED
    assert window_repo.active_window.window_index == 12
    assert window_repo.active_window.last_mode == DrawMode.TRIPLET
    assert draws[-1].perm_code is not None
    assert draw_repo.insert_calls == 12


def test_pair_sequence_rotates_and_uses_last_full_order():
    window_repo = FakeWindowRepo(_make_active_window(last_full_order=PermCode.P231))
    draw_repo = FakeDrawRepo()
    service = DrawService(window_repo, draw_repo)

    first = _run(service.execute(_make_request(True, True, False)))
    second = _run(service.execute(_make_request(True, True, False)))

    assert first.mode == DrawMode.PAIR
    assert first.derived_from_last_full_order is True
    assert first.pair_cycle_index == 1
    assert (first.pos1, first.pos2) == (2, 1)

    assert second.pair_cycle_index == 0
    assert (second.pos1, second.pos2) == (1, 2)
    assert window_repo.update_calls == 0
    assert window_repo.active_window.last_mode == DrawMode.TRIPLET


def test_single_and_skip_outputs():
    window_repo = FakeWindowRepo(None)
    draw_repo = FakeDrawRepo()
    service = DrawService(window_repo, draw_repo)

    single = _run(service.execute(_make_request(True, False, False)))
    skip = _run(service.execute(_make_request(False, False, False)))

    assert single.mode == DrawMode.SINGLE
    assert single.pos1 == 1
    assert single.pos2 is None
    assert single.pos3 is None
    assert single.stop_morning == 1
    assert single.stop_midday == 1

    assert skip.mode == DrawMode.SKIP
    assert skip.pos1 is None
    assert skip.pos2 is None
    assert skip.pos3 is None
    assert skip.stop_morning is None
    assert skip.stop_midday is None


def test_missing_active_window_creates_new_window_before_draw():
    window_repo = FakeWindowRepo(None)
    draw_repo = FakeDrawRepo()
    service = DrawService(window_repo, draw_repo)

    draw = _run(service.execute(_make_request(True, True, True)))

    assert window_repo.insert_calls == 1
    assert draw.window_id == window_repo.active_window.window_id
    assert draw.mode == DrawMode.TRIPLET
    assert draw.window_index == 0


def test_duplicate_request_id_returns_existing_draw_without_persisting():
    existing = Draw(
        id=99,
        draw_ts=datetime.now(tz=timezone.utc),
        draw_date=date(2025, 1, 15),
        request_id=uuid4(),
        window_id="ABCD1234",
        mode=DrawMode.SKIP,
        present_mask=0,
        window_index=None,
        active_window_index_snapshot=None,
        perm_code=None,
        derived_from_last_full_order=False,
        is_effective=True,
        superseded_by_draw_id=None,
        pair_key=None,
        pair_cycle_index=None,
        pos1=None,
        pos2=None,
        pos3=None,
        stop_morning=None,
        stop_midday=None,
        algorithm_version="1.0.0",
        seed_material_hash="b" * 64,
        note=None,
    )
    window_repo = FakeWindowRepo(None)
    draw_repo = FakeDrawRepo()
    draw_repo.draws.append(existing)
    service = DrawService(window_repo, draw_repo)

    result = _run(
        service.execute(
            _make_request(False, False, False, request_id=existing.request_id)
        )
    )

    assert result is existing
    assert draw_repo.insert_calls == 0
    assert window_repo.insert_calls == 0


def test_uq_active_window_conflict_retries_once(monkeypatch):
    window_repo = FakeWindowRepo(None)
    window_repo.fail_first_insert_constraint = "uq_active_window"
    draw_repo = FakeDrawRepo()
    service = DrawService(window_repo, draw_repo)

    monkeypatch.setattr(
        "core.draw_service.pg_errors.UniqueViolation",
        FakeUniqueViolation,
    )

    draw = _run(service.execute(_make_request(True, True, True)))

    assert draw.mode == DrawMode.TRIPLET
    assert window_repo.insert_calls == 2
    assert draw_repo.insert_calls == 1


def test_uq_effective_draw_per_date_returns_existing_draw(monkeypatch):
    existing = Draw(
        id=101,
        draw_ts=datetime.now(tz=timezone.utc),
        draw_date=date(2025, 1, 15),
        request_id=uuid4(),
        window_id="ABCD1234",
        mode=DrawMode.TRIPLET,
        present_mask=7,
        window_index=0,
        active_window_index_snapshot=0,
        perm_code=PermCode.P123,
        derived_from_last_full_order=False,
        is_effective=True,
        superseded_by_draw_id=None,
        pair_key=None,
        pair_cycle_index=None,
        pos1=1,
        pos2=2,
        pos3=3,
        stop_morning=1,
        stop_midday=2,
        algorithm_version="1.0.0",
        seed_material_hash="c" * 64,
        note=None,
    )
    window_repo = FakeWindowRepo(None)
    draw_repo = FakeDrawRepo()
    draw_repo.fail_first_insert_constraint = "uq_effective_draw_per_date"
    draw_repo.draws.append(existing)
    service = DrawService(window_repo, draw_repo)

    monkeypatch.setattr(
        "core.draw_service.pg_errors.UniqueViolation",
        FakeUniqueViolation,
    )

    result = _run(service.execute(_make_request(True, True, True)))

    assert result is existing
    assert draw_repo.insert_calls == 1
