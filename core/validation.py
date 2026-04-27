"""
core/validation.py
Eingabevalidierung für DrawRequest und Geschäftsregeln.
"""
from __future__ import annotations

from datetime import date, timedelta
from uuid import UUID

from core.models import DrawRequest, DrawMode, MASK_LEON, MASK_EMMI, MASK_ELSA

DRAW_DATE_MAX_PAST_DAYS = 7
DRAW_DATE_MAX_FUTURE_DAYS = 1


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

    for field_name in ("leon_present", "emmi_present", "elsa_present"):
        value = getattr(request, field_name)
        if not isinstance(value, bool):
            raise ValidationError(
                field_name,
                f"{field_name} muss bool sein, erhalten: {type(value).__name__}",
            )

    today = date.today()
    earliest_draw_date = today - timedelta(days=DRAW_DATE_MAX_PAST_DAYS)
    latest_draw_date = today + timedelta(days=DRAW_DATE_MAX_FUTURE_DAYS)
    if request.draw_date < earliest_draw_date:
        raise ValidationError(
            "draw_date",
            (
                f"draw_date darf höchstens {DRAW_DATE_MAX_PAST_DAYS} Tage "
                f"in der Vergangenheit liegen: {request.draw_date.isoformat()}"
            ),
        )
    if request.draw_date > latest_draw_date:
        raise ValidationError(
            "draw_date",
            (
                f"draw_date darf höchstens {DRAW_DATE_MAX_FUTURE_DAYS} Tag "
                f"in der Zukunft liegen: {request.draw_date.isoformat()}"
            ),
        )

    # present_mask muss im Bereich 0..7 liegen
    mask = request.present_mask
    if not (0 <= mask <= 7):
        raise ValidationError("present_mask", f"Ungültiger Wert: {mask}")
