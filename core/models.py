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

REPLAY_FORMAT_VERSION = "1"

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


def derive_draw_mode_from_presence(
    leon_present: object,
    emmi_present: object,
    elsa_present: object,
) -> DrawMode:
    """
    Leitet den fachlichen Modus ausschließlich aus Anwesenheit ab.

    Nur der boolesche Wert ``True`` zählt als anwesend. Alle anderen Werte
    werden als abwesend behandelt, damit die Ableitung bei unerwarteten
    Eingaben nicht kippt.
    """
    present_count = sum(
        value is True for value in (leon_present, emmi_present, elsa_present)
    )
    if present_count == 3:
        return DrawMode.TRIPLET
    if present_count == 2:
        return DrawMode.PAIR
    if present_count == 1:
        return DrawMode.SINGLE
    return DrawMode.SKIP


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
    replay_context_hash:          str
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
        return derive_draw_mode_from_presence(
            self.leon_present,
            self.emmi_present,
            self.elsa_present,
        )

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
class DrawContext:
    """
    Expliziter fachlicher Kontext für die Berechnung eines Draws.

    Der Kontext bündelt die Eingabe und die aus der Persistenz abgeleiteten
    Referenzwerte, damit der Algorithmus nicht mehr aus verstreuten Feldern
    zusammengesetzt werden muss.
    """
    request: DrawRequest
    active_window: Optional[FairnessWindow]
    latest_effective_draw: Optional[Draw] = None
    last_pair_draw: Optional[Draw] = None
    pair_cycle_index: Optional[int] = None
    pair_last_full_order: Optional[PermCode] = None
    pair_window_id: Optional[str] = None
    pair_window_index: Optional[int] = None

    @classmethod
    def from_request(
        cls,
        request: DrawRequest,
        active_window: Optional[FairnessWindow] = None,
        *,
        latest_effective_draw: Optional[Draw] = None,
        last_pair_draw: Optional[Draw] = None,
        pair_cycle_index: Optional[int] = None,
        pair_last_full_order: Optional[PermCode] = None,
        pair_window_id: Optional[str] = None,
        pair_window_index: Optional[int] = None,
    ) -> "DrawContext":
        return cls(
            request=request,
            active_window=active_window,
            latest_effective_draw=latest_effective_draw,
            last_pair_draw=last_pair_draw,
            pair_cycle_index=pair_cycle_index,
            pair_last_full_order=pair_last_full_order,
            pair_window_id=pair_window_id,
            pair_window_index=pair_window_index,
        )

    # If the canonical replay format changes, increment REPLAY_FORMAT_VERSION.
    # Existing stored replay_context_hash values become non-reproducible and
    # require a database migration or hash recomputation.
    def replay_material(self, seed_hash: str) -> str:
        """Kanonische Replay-Beschreibung für Audit und Reproduzierbarkeit."""

        def _ref_draw(draw: Optional[Draw]) -> str:
            if draw is None:
                return "none"
            return "|".join(
                [
                    f"id={draw.id}",
                    f"mode={draw.mode.value}",
                    f"date={draw.draw_date.isoformat()}",
                    f"window_id={draw.window_id or ''}",
                    f"window_index={'' if draw.window_index is None else draw.window_index}",
                    f"perm_code={draw.perm_code.value if draw.perm_code else ''}",
                    f"pair_key={draw.pair_key.value if draw.pair_key else ''}",
                    f"pair_cycle_index={'' if draw.pair_cycle_index is None else draw.pair_cycle_index}",
                    f"derived={int(draw.derived_from_last_full_order)}",
                    f"effective={int(draw.is_effective)}",
                    f"superseded_by_draw_id={'' if draw.superseded_by_draw_id is None else draw.superseded_by_draw_id}",
                ]
            )

        def _ref_window(window: Optional[FairnessWindow]) -> str:
            if window is None:
                return "none"
            return "|".join(
                [
                    f"id={window.id}",
                    f"window_id={window.window_id}",
                    f"status={window.window_status.value}",
                    f"window_index={window.window_index}",
                    f"last_full_order={window.last_full_order.value if window.last_full_order else ''}",
                    f"last_full_draw_date={'' if window.last_full_draw_date is None else window.last_full_draw_date.isoformat()}",
                    f"last_mode={window.last_mode.value if window.last_mode else ''}",
                    f"seed_material_hash={window.seed_material_hash}",
                ]
            )

        request = self.request
        parts = [
            f"v={REPLAY_FORMAT_VERSION}",
            f"seed_hash={seed_hash}",
            f"request_id={request.request_id}",
            f"draw_date={request.draw_date.isoformat()}",
            f"present_mask={request.present_mask}",
            f"active_window={_ref_window(self.active_window)}",
            f"latest_effective_draw={_ref_draw(self.latest_effective_draw)}",
            f"last_pair_draw={_ref_draw(self.last_pair_draw)}",
            f"pair_cycle_index={'' if self.pair_cycle_index is None else self.pair_cycle_index}",
            f"pair_last_full_order={self.pair_last_full_order.value if self.pair_last_full_order else ''}",
            f"pair_window_id={self.pair_window_id or ''}",
            f"pair_window_index={'' if self.pair_window_index is None else self.pair_window_index}",
        ]
        return "||".join(parts)


@dataclass
class SystemConfig:
    """Repräsentation einer Zeile in system_config."""
    key_name:   str
    value:      str
    updated_at: datetime
