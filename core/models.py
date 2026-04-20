"""
core/models.py
Domänenmodelle für KIDS_CONTROLLER.
Kinder-IDs: 1=Leon, 2=Emmi, 3=Elsa
"""
from __future__ import annotations

import enum
from dataclasses import dataclass, field
from datetime import date, datetime
from typing import Optional
from uuid import UUID


# ---------------------------------------------------------------------------
# Konstanten
# ---------------------------------------------------------------------------

LEON_ID: int = 1
EMMI_ID: int = 2
ELSA_ID: int = 3

KIDS: dict[int, str] = {
    LEON_ID: "Leon",
    EMMI_ID: "Emmi",
    ELSA_ID: "Elsa",
}

# present_mask Bitmasken
MASK_LEON: int = 1   # 0b001
MASK_EMMI: int = 2   # 0b010
MASK_ELSA: int = 4   # 0b100
MASK_ALL:  int = 7   # 0b111


# ---------------------------------------------------------------------------
# ENUM-Spiegelungen (Python-Seite)
# ---------------------------------------------------------------------------

class WindowStatus(str, enum.Enum):
    ACTIVE    = "ACTIVE"
    COMPLETED = "COMPLETED"


class DrawMode(str, enum.Enum):
    TRIPLET = "TRIPLET"
    PAIR    = "PAIR"
    SINGLE  = "SINGLE"
    SKIP    = "SKIP"


class PermCode(str, enum.Enum):
    P123 = "123"
    P132 = "132"
    P213 = "213"
    P231 = "231"
    P312 = "312"
    P321 = "321"

    def to_tuple(self) -> tuple[int, int, int]:
        """Liefert (pos1, pos2, pos3) als Integer-Tupel."""
        return (int(self.value[0]), int(self.value[1]), int(self.value[2]))


class PairKey(str, enum.Enum):
    P12 = "12"
    P13 = "13"
    P23 = "23"

    def to_ids(self) -> tuple[int, int]:
        return (int(self.value[0]), int(self.value[1]))


# ---------------------------------------------------------------------------
# Domänenobjekte
# ---------------------------------------------------------------------------

@dataclass
class FairnessWindow:
    """Repräsentation einer Zeile in fairness_windows."""
    id:                   int
    window_id:            str          # CHAR(8)
    window_start_date:    date
    window_status:        WindowStatus
    window_index:         int          # 0-11 = ACTIVE, 12 = COMPLETED
    window_size:          int
    permutation_sequence: list[str]    # Liste von PermCode-Werten (JSONB)
    last_full_order:      Optional[PermCode]
    last_full_draw_date:  Optional[date]
    # Fachlich nur der letzte TRIPLET-/Fensterzustand, kein globaler letzter Modus.
    last_mode:            Optional[DrawMode]
    seed_material_hash:   str          # CHAR(64)
    shuffle_algorithm:    str
    algorithm_version:    str
    created_at:           datetime
    updated_at:           datetime


@dataclass
class Draw:
    """Repräsentation einer Zeile in draws."""
    id:                           int
    draw_ts:                      datetime
    draw_date:                    date
    request_id:                   UUID          # NOT NULL
    window_id:                    Optional[str]
    mode:                         DrawMode
    present_mask:                 int           # SMALLINT, Bitmaske
    window_index:                 Optional[int] # nur TRIPLET
    active_window_index_snapshot: Optional[int]
    perm_code:                    Optional[PermCode]  # nur TRIPLET
    derived_from_last_full_order: bool
    is_effective:                 bool
    superseded_by_draw_id:        Optional[int]
    pair_key:                     Optional[PairKey]
    pair_cycle_index:             Optional[int]  # 0 oder 1, nur PAIR
    pos1:                         Optional[int]
    pos2:                         Optional[int]
    pos3:                         Optional[int]  # nur TRIPLET
    stop_morning:                 Optional[int]
    stop_midday:                  Optional[int]
    algorithm_version:            str
    seed_material_hash:           str
    note:                         Optional[str]


@dataclass
class DrawRequest:
    """Eingehende Anfrage für einen Auslosungs-Vorgang."""
    leon_present: bool
    emmi_present: bool
    elsa_present: bool
    request_id:   UUID
    draw_date:    date = field(default_factory=date.today)

    @property
    def present_mask(self) -> int:
        mask = 0
        if self.leon_present:
            mask |= MASK_LEON
        if self.emmi_present:
            mask |= MASK_EMMI
        if self.elsa_present:
            mask |= MASK_ELSA
        return mask

    @property
    def present_count(self) -> int:
        return bin(self.present_mask).count("1")

    def determine_mode(self) -> DrawMode:
        count = self.present_count
        if count == 3:
            return DrawMode.TRIPLET
        if count == 2:
            return DrawMode.PAIR
        if count == 1:
            return DrawMode.SINGLE
        return DrawMode.SKIP

    def present_ids(self) -> list[int]:
        result = []
        if self.leon_present:
            result.append(LEON_ID)
        if self.emmi_present:
            result.append(EMMI_ID)
        if self.elsa_present:
            result.append(ELSA_ID)
        return result


@dataclass
class SystemConfig:
    """Repräsentation einer Zeile in system_config."""
    key_name:   str
    value:      str
    updated_at: datetime
