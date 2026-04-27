"""
core/algorithm.py
Auslosungsalgorithmus für KIDS_CONTROLLER.

Regeln:
- TRIPLET: Fisher-Yates-Shuffle eines 12er-Fensters (6 Perm × 2)
- PAIR:    AB/BA-Rotation; erste Orientierung kann aus last_full_order abgeleitet werden
- SINGLE:  pos1 = Kind, pos2 = pos3 = None
- SKIP:    alle Positionen None
"""
from __future__ import annotations

import hashlib
import random
import secrets
import string
from datetime import date, datetime, timezone
from typing import Optional
from uuid import UUID

from core.models import (
    Draw,
    DrawContext,
    DrawMode,
    DrawRequest,
    FairnessWindow,
    PairKey,
    PermCode,
    WindowStatus,
)

ALGORITHM_VERSION = "1.0.0"
SHUFFLE_ALGORITHM = "fisher_yates"
WINDOW_SIZE       = 12

# Alle 6 Permutationen (je 2x im Fenster = 12 Züge)
_ALL_PERM_CODES: list[str] = ["123", "132", "213", "231", "312", "321"]


# ---------------------------------------------------------------------------
# Hilfsfunktionen
# ---------------------------------------------------------------------------

def _generate_window_id() -> str:
    """Liefert eine 8-stellige alphanumerische Kurzkennung (CHAR(8))."""
    alphabet = string.ascii_uppercase + string.digits
    return "".join(secrets.choice(alphabet) for _ in range(8))


def _compute_hash(material: str) -> str:
    """SHA-256-Hash als Hex-String (64 Zeichen)."""
    return hashlib.sha256(material.encode("utf-8")).hexdigest()


def _seed_int_from_hash(seed_hash: str) -> int:
    """
    Wandelt einen Hex-Hash in einen stabilen Integer-Seed für random.Random um.

    Der vollständige Hash wird verwendet, damit die Fensterfolge reproduzierbar
    bleibt und nicht von einer gekürzten Seed-Repräsentation abhängt.
    """
    return int(seed_hash, 16)


def _shuffle_permutation_sequence(seed: Optional[int] = None) -> list[str]:
    """
    Erstellt eine gemischte 12er-Sequenz: jede der 6 Perm-Codes 2× vorhanden.
    Fisher-Yates via random.shuffle (mit optionalem Seed für Tests).
    """
    sequence = _ALL_PERM_CODES * 2
    rng = random.Random(seed)
    rng.shuffle(sequence)
    return sequence


def _seed_material_for_window(window_id: str, draw_date: date) -> str:
    return f"WINDOW:{window_id}:DATE:{draw_date.isoformat()}"


def _pair_key_for_mask(present_mask: int) -> PairKey:
    """Bestimmt den PairKey aus der Bitmaske bei genau 2 Anwesenden."""
    # Leon=1 (bit 0), Emmi=2 (bit 1), Elsa=4 (bit 2)
    if present_mask == 3:   # Leon + Emmi
        return PairKey.P12
    if present_mask == 5:   # Leon + Elsa
        return PairKey.P13
    if present_mask == 6:   # Emmi + Elsa
        return PairKey.P23
    raise ValueError(f"Ungültige present_mask für PAIR: {present_mask}")


def _derive_pair_order_from_perm(
    perm_code: PermCode,
    pair_key: PairKey,
) -> tuple[int, int]:
    """
    Leitet die Reihenfolge eines Paares aus dem letzten TRIPLET perm_code ab.
    Das erste Kind im perm_code, das im Paar vorkommt, ist pos1.
    """
    ids = list(perm_code.to_tuple())
    a, b = pair_key.to_ids()
    for kid_id in ids:
        if kid_id == a:
            return (a, b)
        if kid_id == b:
            return (b, a)
    return (a, b)  # Fallback


def _pair_positions_for_state(
    pair_key: PairKey,
    *,
    last_full_order: Optional[PermCode] = None,
    pair_cycle_index: Optional[int] = None,
) -> tuple[int, int, bool, int]:
    """
    Pure Hilfsfunktion für PAIR.

    Rückgabe: (pos1, pos2, derived_from_last_full_order, cycle_index).
    Die Runtime-Historie bleibt in DrawService; diese Funktion berechnet nur
    Positionen aus dem bereits bekannten Zustand.
    """
    a, b = pair_key.to_ids()

    if pair_cycle_index is not None:
        pos1, pos2 = (a, b) if pair_cycle_index == 0 else (b, a)
        return pos1, pos2, False, pair_cycle_index

    if last_full_order is not None:
        pos1, pos2 = _derive_pair_order_from_perm(last_full_order, pair_key)
        derived_cycle_index = 0 if (pos1, pos2) == (a, b) else 1
        return pos1, pos2, True, derived_cycle_index

    return a, b, False, 0


def _compute_seed_hash(request_id: UUID, draw_date: date, mode: DrawMode) -> str:
    material = f"REQ:{request_id}:DATE:{draw_date.isoformat()}:MODE:{mode.value}"
    return _compute_hash(material)


def build_draw_from_context(
    context: DrawContext,
) -> tuple[Draw, Optional[FairnessWindow]]:
    """
    Berechnet einen neuen Draw und den (ggf. aktualisierten) FairnessWindow.

    Rückgabe:
        (draw, updated_window)
        - updated_window ist None bei SKIP/SINGLE/PAIR
        - updated_window ist ein neues oder fortgesetztes Fenster bei TRIPLET
    """
    request = context.request
    active_window = context.active_window
    mode = request.determine_mode()
    now  = datetime.now(tz=timezone.utc)
    seed_hash = _compute_seed_hash(request.request_id, request.draw_date, mode)
    replay_context_hash = _compute_hash(context.replay_material(seed_hash))

    if mode == DrawMode.SKIP:
        return _build_skip_draw(request, now, seed_hash, replay_context_hash), None

    if mode == DrawMode.SINGLE:
        return _build_single_draw(request, now, seed_hash, replay_context_hash), None

    if mode == DrawMode.PAIR:
        return _build_pair_draw_from_context(context, now, seed_hash, replay_context_hash), None

    # TRIPLET
    return _build_triplet_draw(request, active_window, now, seed_hash, replay_context_hash)


# ---------------------------------------------------------------------------
# SKIP
# ---------------------------------------------------------------------------

def _build_skip_draw(
    request:   DrawRequest,
    now:       datetime,
    seed_hash: str,
    replay_context_hash: str,
) -> Draw:
    return Draw(
        id=0,
        draw_ts=now,
        draw_date=request.draw_date,
        request_id=request.request_id,
        window_id=None,
        mode=DrawMode.SKIP,
        present_mask=request.present_mask,
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
        algorithm_version=ALGORITHM_VERSION,
        seed_material_hash=seed_hash,
        replay_context_hash=replay_context_hash,
        note="SKIP – kein Kind anwesend",
    )


# ---------------------------------------------------------------------------
# SINGLE
# ---------------------------------------------------------------------------

def _build_single_draw(
    request:   DrawRequest,
    now:       datetime,
    seed_hash: str,
    replay_context_hash: str,
) -> Draw:
    kid_id = request.present_ids()[0]
    return Draw(
        id=0,
        draw_ts=now,
        draw_date=request.draw_date,
        request_id=request.request_id,
        window_id=None,
        mode=DrawMode.SINGLE,
        present_mask=request.present_mask,
        window_index=None,
        active_window_index_snapshot=None,
        perm_code=None,
        derived_from_last_full_order=False,
        is_effective=True,
        superseded_by_draw_id=None,
        pair_key=None,
        pair_cycle_index=None,
        pos1=kid_id,
        pos2=None,
        pos3=None,
        stop_morning=kid_id,
        stop_midday=kid_id,
        algorithm_version=ALGORITHM_VERSION,
        seed_material_hash=seed_hash,
        replay_context_hash=replay_context_hash,
        note=f"SINGLE – nur Kind {kid_id}",
    )


# ---------------------------------------------------------------------------
# PAIR
# ---------------------------------------------------------------------------

def _build_pair_draw_from_context(
    context: DrawContext,
    now: datetime,
    seed_hash: str,
    replay_context_hash: str,
) -> Draw:
    request = context.request
    active_window = context.active_window
    pair_key = _pair_key_for_mask(request.present_mask)
    source_window_id = context.pair_window_id
    source_window_index = context.pair_window_index
    last_full_order = context.pair_last_full_order
    if (
        last_full_order is None
        and active_window is not None
        and active_window.last_full_order is not None
        and active_window.last_mode == DrawMode.TRIPLET
    ):
        last_full_order = active_window.last_full_order
        if source_window_id is None:
            source_window_id = active_window.window_id
        if source_window_index is None:
            source_window_index = active_window.window_index
    if last_full_order is None:
        latest_effective_draw = context.latest_effective_draw
        if (
            latest_effective_draw is not None
            and latest_effective_draw.mode == DrawMode.TRIPLET
            and latest_effective_draw.perm_code is not None
        ):
            last_full_order = latest_effective_draw.perm_code
            if source_window_id is None:
                source_window_id = latest_effective_draw.window_id
            if source_window_index is None:
                source_window_index = latest_effective_draw.window_index

    pos1, pos2, derived, cycle_index = _pair_positions_for_state(
        pair_key,
        last_full_order=last_full_order,
        pair_cycle_index=context.pair_cycle_index,
    )

    return Draw(
        id=0,
        draw_ts=now,
        draw_date=request.draw_date,
        request_id=request.request_id,
        window_id=(
            source_window_id
            if source_window_id is not None
            else active_window.window_id if active_window else None
        ),
        mode=DrawMode.PAIR,
        present_mask=request.present_mask,
        window_index=None,
        active_window_index_snapshot=(
            source_window_index
            if source_window_index is not None
            else active_window.window_index if active_window else None
        ),
        perm_code=None,
        derived_from_last_full_order=derived,
        is_effective=True,
        superseded_by_draw_id=None,
        pair_key=pair_key,
        pair_cycle_index=cycle_index,
        pos1=pos1,
        pos2=pos2,
        pos3=None,
        stop_morning=pos1,
        stop_midday=pos2,
        algorithm_version=ALGORITHM_VERSION,
        seed_material_hash=seed_hash,
        replay_context_hash=replay_context_hash,
        note=None,
    )


# ---------------------------------------------------------------------------
# TRIPLET
# ---------------------------------------------------------------------------

def _build_triplet_draw(
    request:       DrawRequest,
    active_window: Optional[FairnessWindow],
    now:           datetime,
    seed_hash:     str,
    replay_context_hash: str,
) -> tuple[Draw, FairnessWindow]:
    """
    Liest den nächsten perm_code aus dem aktiven Fenster oder erzeugt ein neues.
    Dreierregel: window_index 0..11 = ACTIVE, nach Index 11 → COMPLETED (12).
    """
    if active_window is None:
        # Neues Fenster anlegen
        window_id  = _generate_window_id()
        w_seed_mat = _seed_material_for_window(window_id, request.draw_date)
        w_hash     = _compute_hash(w_seed_mat)
        perm_seq   = _shuffle_permutation_sequence(seed=_seed_int_from_hash(w_hash))
        window = FairnessWindow(
            id=0,
            window_id=window_id,
            window_start_date=request.draw_date,
            window_status=WindowStatus.ACTIVE,
            window_index=0,
            window_size=WINDOW_SIZE,
            permutation_sequence=perm_seq,
            last_full_order=None,
            last_full_draw_date=None,
            last_mode=None,
            seed_material_hash=w_hash,
            shuffle_algorithm=SHUFFLE_ALGORITHM,
            algorithm_version=ALGORITHM_VERSION,
            created_at=now,
            updated_at=now,
        )
    else:
        window = active_window

    # Permutation aus Sequenz lesen
    idx           = window.window_index
    if idx < 0 or idx >= WINDOW_SIZE:
        raise IndexError(
            f"Ungültiger window_index {idx}; erwartet 0..{WINDOW_SIZE - 1}"
        )
    perm_code_str = window.permutation_sequence[idx]
    perm_code     = PermCode(perm_code_str)
    pos1, pos2, pos3 = perm_code.to_tuple()

    # Fenster-Index vorwärtsbewegen
    new_index  = idx + 1
    new_status = WindowStatus.COMPLETED if new_index >= WINDOW_SIZE else WindowStatus.ACTIVE

    updated_window = FairnessWindow(
        id=window.id,
        window_id=window.window_id,
        window_start_date=window.window_start_date,
        window_status=new_status,
        window_index=new_index,
        window_size=window.window_size,
        permutation_sequence=window.permutation_sequence,
        last_full_order=perm_code,
        last_full_draw_date=request.draw_date,
        last_mode=DrawMode.TRIPLET,
        seed_material_hash=window.seed_material_hash,
        shuffle_algorithm=window.shuffle_algorithm,
        algorithm_version=window.algorithm_version,
        created_at=window.created_at,
        updated_at=now,
    )

    draw = Draw(
        id=0,
        draw_ts=now,
        draw_date=request.draw_date,
        request_id=request.request_id,
        window_id=window.window_id,
        mode=DrawMode.TRIPLET,
        present_mask=request.present_mask,
        window_index=idx,
        active_window_index_snapshot=idx,
        perm_code=perm_code,
        derived_from_last_full_order=False,
        is_effective=True,
        superseded_by_draw_id=None,
        pair_key=None,
        pair_cycle_index=None,
        pos1=pos1,
        pos2=pos2,
        pos3=pos3,
        stop_morning=pos1,
        stop_midday=pos2,
        algorithm_version=ALGORITHM_VERSION,
        seed_material_hash=seed_hash,
        replay_context_hash=replay_context_hash,
        note=None,
    )
    return draw, updated_window


# ---------------------------------------------------------------------------
# Pair-Zyklus-Rotation (für DrawService mit DB-Kontext)
# ---------------------------------------------------------------------------

def next_pair_cycle_index(last_pair_cycle_index: Optional[int]) -> int:
    """AB/BA-Rotation: 0 → 1 → 0 → ..."""
    if last_pair_cycle_index is None:
        return 0
    if last_pair_cycle_index not in (0, 1):
        raise ValueError(
            f"Ungültiger pair_cycle_index {last_pair_cycle_index}; erwartet 0 oder 1"
        )
    return 1 - last_pair_cycle_index
