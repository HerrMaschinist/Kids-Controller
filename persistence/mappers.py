"""
persistence/mappers.py
Mapping zwischen psycopg v3 dict-Rows und Domänenobjekten.
psycopg v3 mit dict_row liefert dict; Feldnamen entsprechen 1:1 den SQL-Spaltennamen.
"""
from __future__ import annotations

import json
from typing import Any, Optional
from uuid import UUID

from core.models import (
    Draw,
    DrawMode,
    FairnessWindow,
    PairKey,
    PermCode,
    SystemConfig,
    WindowStatus,
)


def record_to_fairness_window(row: dict) -> FairnessWindow:
    """psycopg v3 dict-Row → FairnessWindow."""
    perm_seq_raw = row["permutation_sequence"]
    if isinstance(perm_seq_raw, str):
        perm_seq = json.loads(perm_seq_raw)
    elif isinstance(perm_seq_raw, list):
        perm_seq = perm_seq_raw
    else:
        perm_seq = list(perm_seq_raw)

    last_full_order_raw: Optional[str] = row["last_full_order"]
    # last_mode ist im aktuellen Schema ein TRIPLET-/Fensterzustand.
    last_mode_raw: Optional[str] = row["last_mode"]

    return FairnessWindow(
        id=row["id"],
        window_id=row["window_id"],
        window_start_date=row["window_start_date"],
        window_status=WindowStatus(row["window_status"]),
        window_index=row["window_index"],
        window_size=row["window_size"],
        permutation_sequence=perm_seq,
        last_full_order=PermCode(last_full_order_raw) if last_full_order_raw else None,
        last_full_draw_date=row["last_full_draw_date"],
        last_mode=DrawMode(last_mode_raw) if last_mode_raw else None,
        seed_material_hash=row["seed_material_hash"],
        shuffle_algorithm=row["shuffle_algorithm"],
        algorithm_version=row["algorithm_version"],
        created_at=row["created_at"],
        updated_at=row["updated_at"],
    )


def record_to_draw(row: dict) -> Draw:
    """psycopg v3 dict-Row → Draw."""
    perm_code_raw: Optional[str] = row["perm_code"]
    pair_key_raw: Optional[str] = row["pair_key"]
    request_id_raw = row["request_id"]

    return Draw(
        id=row["id"],
        draw_ts=row["draw_ts"],
        draw_date=row["draw_date"],
        request_id=UUID(str(request_id_raw)),
        window_id=row["window_id"],
        mode=DrawMode(row["mode"]),
        present_mask=row["present_mask"],
        window_index=row["window_index"],
        active_window_index_snapshot=row["active_window_index_snapshot"],
        perm_code=PermCode(perm_code_raw) if perm_code_raw else None,
        derived_from_last_full_order=row["derived_from_last_full_order"],
        is_effective=row["is_effective"],
        superseded_by_draw_id=row["superseded_by_draw_id"],
        pair_key=PairKey(pair_key_raw) if pair_key_raw else None,
        pair_cycle_index=row["pair_cycle_index"],
        pos1=row["pos1"],
        pos2=row["pos2"],
        pos3=row["pos3"],
        stop_morning=row["stop_morning"],
        stop_midday=row["stop_midday"],
        algorithm_version=row["algorithm_version"],
        seed_material_hash=row["seed_material_hash"],
        replay_context_hash=row.get("replay_context_hash") or row["seed_material_hash"],
        note=row["note"],
    )


def record_to_system_config(row: dict) -> SystemConfig:
    return SystemConfig(
        key_name=row["key_name"],
        value=row["value"],
        updated_at=row["updated_at"],
    )


def draw_to_insert_params(draw: Draw) -> dict[str, Any]:
    """Draw → dict für INSERT INTO draws."""
    return {
        "draw_ts":                      draw.draw_ts,
        "draw_date":                    draw.draw_date,
        "request_id":                   str(draw.request_id),
        "window_id":                    draw.window_id,
        "mode":                         draw.mode.value,
        "present_mask":                 draw.present_mask,
        "window_index":                 draw.window_index,
        "active_window_index_snapshot": draw.active_window_index_snapshot,
        "perm_code":                    draw.perm_code.value if draw.perm_code else None,
        "derived_from_last_full_order": draw.derived_from_last_full_order,
        "is_effective":                 draw.is_effective,
        "superseded_by_draw_id":        draw.superseded_by_draw_id,
        "pair_key":                     draw.pair_key.value if draw.pair_key else None,
        "pair_cycle_index":             draw.pair_cycle_index,
        "pos1":                         draw.pos1,
        "pos2":                         draw.pos2,
        "pos3":                         draw.pos3,
        "stop_morning":                 draw.stop_morning,
        "stop_midday":                  draw.stop_midday,
        "algorithm_version":            draw.algorithm_version,
        "seed_material_hash":           draw.seed_material_hash,
        "note":                         draw.note,
        "replay_context_hash":          draw.replay_context_hash,
    }


def window_to_insert_params(window: FairnessWindow) -> dict[str, Any]:
    """FairnessWindow → dict für INSERT INTO fairness_windows."""
    return {
        "window_id":            window.window_id,
        "window_start_date":    window.window_start_date,
        "window_status":        window.window_status.value,
        "window_index":         window.window_index,
        "window_size":          window.window_size,
        "permutation_sequence": json.dumps(window.permutation_sequence),
        "last_full_order":      window.last_full_order.value if window.last_full_order else None,
        "last_full_draw_date":  window.last_full_draw_date,
        "last_mode":            window.last_mode.value if window.last_mode else None,
        "seed_material_hash":   window.seed_material_hash,
        "shuffle_algorithm":    window.shuffle_algorithm,
        "algorithm_version":    window.algorithm_version,
    }


def window_to_update_params(window: FairnessWindow) -> dict[str, Any]:
    """FairnessWindow → dict für UPDATE fairness_windows."""
    return {
        "id":                   window.id,
        "window_status":        window.window_status.value,
        "window_index":         window.window_index,
        "last_full_order":      window.last_full_order.value if window.last_full_order else None,
        "last_full_draw_date":  window.last_full_draw_date,
        "last_mode":            window.last_mode.value if window.last_mode else None,
        "updated_at":           window.updated_at,
    }
