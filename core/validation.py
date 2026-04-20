"""
core/validation.py
Eingabevalidierung für DrawRequest und Geschäftsregeln.
"""
from __future__ import annotations

from uuid import UUID

from core.models import DrawRequest, DrawMode, MASK_LEON, MASK_EMMI, MASK_ELSA


class ValidationError(Exception):
    """Fachlicher Validierungsfehler."""
    def __init__(self, field: str, message: str) -> None:
        self.field   = field
        self.message = message
        super().__init__(f"{field}: {message}")


def validate_draw_request(request: DrawRequest) -> None:
    """
    Prüft einen DrawRequest auf fachliche Korrektheit.
    Wirft ValidationError bei Verstößen.
    """
    # request_id ist Pflicht und darf nicht leer oder die Null-UUID sein
    if request.request_id is None:
        raise ValidationError("request_id", "request_id ist Pflicht")
    if request.request_id == UUID(int=0):
        raise ValidationError("request_id", "request_id darf nicht die Null-UUID sein")

    # present_mask muss im Bereich 0..7 liegen
    mask = request.present_mask
    if not (0 <= mask <= 7):
        raise ValidationError("present_mask", f"Ungültiger Wert: {mask}")


def validate_present_mask_is_smallint(value: object) -> None:
    """Stellt sicher, dass present_mask kein JSON/dict ist (SMALLINT-Pflicht)."""
    if isinstance(value, (dict, list)):
        raise ValidationError(
            "present_mask",
            "present_mask muss SMALLINT sein, kein JSON/dict",
        )
    if not isinstance(value, int):
        raise ValidationError(
            "present_mask",
            f"present_mask muss int sein, erhalten: {type(value).__name__}",
        )
