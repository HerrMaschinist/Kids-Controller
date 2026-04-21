"""
app/api_routes.py
FastAPI-Router für KIDS_CONTROLLER.

Endpunkt: POST /api/v1/draw
"""
from __future__ import annotations

import logging

from fastapi import APIRouter, Depends, HTTPException, status

from app.dependencies import get_draw_service, get_supervisor_service
from config.settings import get_settings
from config.time import today_in_timezone
from core.draw_service import DrawService
from core.validation import ValidationError
from integrations.homeassistant_adapter import (
    domain_draw_to_ha_response,
    ha_request_to_domain,
)
from integrations.homeassistant_models import HaDrawRequest, HaDrawResponse
from integrations.supervisor_models import SupervisorStatusResponse
from core.supervisor_service import SupervisorService

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/v1", tags=["draw"])


@router.post(
    "/draw",
    response_model=HaDrawResponse,
    status_code=status.HTTP_200_OK,
    summary="Auslosung für heute berechnen",
    description=(
        "Berechnet die Reihenfolge für Leon, Emmi und Elsa basierend auf "
        "Anwesenheit und Fairness-Algorithmus. Idempotent: gleiche request_id "
        "liefert immer dasselbe Ergebnis."
    ),
)
async def post_draw(
    ha_request:   HaDrawRequest = ...,
    draw_service: DrawService   = Depends(get_draw_service),
) -> HaDrawResponse:
    settings = get_settings()
    domain_request = ha_request_to_domain(
        ha_request,
        draw_date=today_in_timezone(settings.controller_timezone),
    )

    try:
        draw = await draw_service.execute(domain_request)
    except ValidationError as exc:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail={"field": exc.field, "message": exc.message},
        ) from exc
    except Exception as exc:
        logger.exception("Unerwarteter Fehler bei Draw request_id=%s", ha_request.request_id)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Interner Serverfehler",
        ) from exc

    return domain_draw_to_ha_response(draw)


@router.get(
    "/health",
    status_code=status.HTTP_200_OK,
    summary="Liveness-Check",
)
async def health_check() -> dict[str, str]:
    return {"status": "ok", "service": "kids_controller"}


@router.get(
    "/status",
    response_model=SupervisorStatusResponse,
    status_code=status.HTTP_200_OK,
    summary="Betriebs- und Supervisor-Status",
)
async def status_check(
    supervisor_service: SupervisorService = Depends(get_supervisor_service),
) -> SupervisorStatusResponse:
    return await supervisor_service.snapshot()
