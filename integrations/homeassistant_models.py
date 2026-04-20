"""
integrations/homeassistant_models.py
Pydantic-Modelle für die Home-Assistant-Schnittstelle.

Feldnamen Request (verbindlich):
  leon_present, emmi_present, elsa_present, request_id

Feldnamen Response (verbindlich):
  draw_id, mode, pos1, pos2, pos3, stop_morning, stop_midday, date

Alias-Entscheidung:
  Das Feld 'date' kollidiert in Pydantic v2 mit dem built-in-Typnamen.
  Intern heißt das Feld 'draw_date'.
  Der Pydantic-Alias 'date' sorgt dafür, dass die JSON-Antwort das Feld
  weiterhin als 'date' serialisiert (via model_dump(by_alias=True)).
"""
from __future__ import annotations

from datetime import date, datetime
from typing import Optional
from uuid import UUID

from pydantic import BaseModel, Field


class HaDrawRequest(BaseModel):
    """Eingehende Anfrage von Home Assistant."""

    leon_present: bool = Field(..., description="Leon ist anwesend")
    emmi_present: bool = Field(..., description="Emmi ist anwesend")
    elsa_present: bool = Field(..., description="Elsa ist anwesend")
    request_id:   UUID = Field(..., description="Pflicht-UUID der Anfrage für Idempotenz")

    model_config = {
        "json_schema_extra": {
            "example": {
                "leon_present": True,
                "emmi_present": True,
                "elsa_present": False,
                "request_id":   "550e8400-e29b-41d4-a716-446655440000",
            }
        }
    }


class HaDrawResponse(BaseModel):
    """
    Antwort an Home Assistant.

    Internes Feld 'draw_date' wird via Alias als 'date' serialisiert.
    Konstruktion: HaDrawResponse.model_validate({..., "date": value})
    Serialisierung: response.model_dump(by_alias=True) → {"date": ...}
    """

    draw_id:      int           = Field(..., description="Primärschlüssel des Draw")
    mode:         str           = Field(..., description="TRIPLET | PAIR | SINGLE | SKIP")
    pos1:         Optional[int] = Field(None, description="Kind-ID auf Position 1")
    pos2:         Optional[int] = Field(None, description="Kind-ID auf Position 2")
    pos3:         Optional[int] = Field(None, description="Kind-ID auf Position 3")
    stop_morning: Optional[int] = Field(None, description="Kind-ID Haltestelle morgens")
    stop_midday:  Optional[int] = Field(None, description="Kind-ID Haltestelle mittags")
    draw_date:    date          = Field(..., alias="date", description="Datum des Draws")
    generated_at: datetime      = Field(..., description="Persistierter Erzeugungszeitpunkt des Draws")

    model_config = {
        "populate_by_name": True,
        "json_schema_extra": {
            "example": {
                "draw_id":      42,
                "mode":         "PAIR",
                "pos1":         1,
                "pos2":         2,
                "pos3":         None,
                "stop_morning": 1,
                "stop_midday":  2,
                "date":         "2025-01-15",
                "generated_at": "2025-01-15T06:42:17Z",
            }
        },
    }


class HaErrorResponse(BaseModel):
    """Fehlerantwort."""
    detail: str
    field:  Optional[str] = None
