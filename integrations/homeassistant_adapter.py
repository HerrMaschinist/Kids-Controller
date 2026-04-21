"""
integrations/homeassistant_adapter.py
Adapter zwischen Home-Assistant-Modellen und Domänenobjekten.

Verantwortlichkeiten:
  - HaDrawRequest  → DrawRequest  (Domäne)
  - Draw           → HaDrawResponse (HA)
"""
from __future__ import annotations

from datetime import date

from config.settings import get_settings
from config.time import today_in_timezone
from core.models import Draw, DrawRequest
from integrations.homeassistant_models import HaDrawRequest, HaDrawResponse


def ha_request_to_domain(ha_req: HaDrawRequest, draw_date: date | None = None) -> DrawRequest:
    """
    Konvertiert eine HaDrawRequest in einen Domänen-DrawRequest.

    Feldmapping (verbindlich):
      ha_req.leon_present → DrawRequest.leon_present
      ha_req.emmi_present → DrawRequest.emmi_present
      ha_req.elsa_present → DrawRequest.elsa_present
      ha_req.request_id   → DrawRequest.request_id
    """
    return DrawRequest(
        request_id=ha_req.request_id,
        leon_present=ha_req.leon_present,
        emmi_present=ha_req.emmi_present,
        elsa_present=ha_req.elsa_present,
        draw_date=draw_date or today_in_timezone(get_settings().controller_timezone),
    )


def domain_draw_to_ha_response(draw: Draw) -> HaDrawResponse:
    """
    Konvertiert einen Domänen-Draw in eine HaDrawResponse.

    Pflichtfelder der Response:
      draw_id, mode, pos1, pos2, pos3, stop_morning, stop_midday, date, generated_at
    """
    # Konstruktion via model_validate mit Alias-Schlüssel "date",
    # damit Pydantic den Alias korrekt auflöst (internes Feld: draw_date).
    return HaDrawResponse.model_validate({
        "draw_id":      draw.id,
        "mode":         draw.mode.value,
        "pos1":         draw.pos1,
        "pos2":         draw.pos2,
        "pos3":         draw.pos3,
        "stop_morning": draw.stop_morning,
        "stop_midday":  draw.stop_midday,
        "date":         draw.draw_date,
        "generated_at": draw.draw_ts,
    })
