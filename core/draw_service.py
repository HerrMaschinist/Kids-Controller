"""
core/draw_service.py
DrawService orchestriert Algorithmus und Persistenz in einer Transaktion.

Transaktionsreihenfolge (verbindlich):
  1. Aktives Fenster mit Sperre lesen (SELECT FOR UPDATE)
  2. Berechnung ausführen
  3. Fenster aktualisieren oder neu anlegen
  4. Draw schreiben
  5. Commit oder Rollback
"""
from __future__ import annotations

import logging

from core.algorithm import (
    build_draw_from_context,
    next_pair_cycle_index,
    _pair_key_for_mask,
)
from core.models import (
    Draw,
    DrawContext,
    DrawMode,
    DrawRequest,
    FairnessWindow,
)
from core.supervisor_state import SupervisorState, get_supervisor_state
from core.validation import validate_draw_request
from integrations.router_client import RouterClient
from persistence.repositories import DrawRepository, WindowRepository
from psycopg import errors as pg_errors

logger = logging.getLogger(__name__)


class DrawService:
    def __init__(
        self,
        window_repo: WindowRepository,
        draw_repo:   DrawRepository,
        router_client: RouterClient | None = None,
        supervisor_state: SupervisorState | None = None,
    ) -> None:
        self._window_repo = window_repo
        self._draw_repo   = draw_repo
        self._router_client = router_client
        self._supervisor_state = supervisor_state or get_supervisor_state()

    async def execute(self, request: DrawRequest) -> Draw:
        """
        Führt einen vollständigen Draw-Vorgang in einer Transaktion aus.
        """
        validate_draw_request(request)

        # Idempotenz: bereits verarbeitete request_id zurückgeben
        existing = await self._draw_repo.find_by_request_id(request.request_id)
        if existing is not None:
            logger.info("Idempotenter Rückgabe für request_id=%s", request.request_id)
            return existing

        saved_draw: Draw | None = None
        effective_window: FairnessWindow | None = None

        for attempt in range(2):
            try:
                async with self._window_repo.transaction() as conn:
                    # Schritt 1: aktives Fenster mit Sperre lesen
                    active_window = await self._window_repo.find_active_with_lock(conn)

                    # Schritt 2: Berechnung
                    mode = request.determine_mode()

                    if mode == DrawMode.PAIR:
                        draw, updated_window = await self._handle_pair(
                            request, active_window, conn
                        )
                    else:
                        draw, updated_window = build_draw_from_context(
                            DrawContext.from_request(request, active_window)
                        )

                    # Schritt 3: Fenster aktualisieren oder neu anlegen
                    if updated_window is not None:
                        if updated_window.id == 0:
                            updated_window = await self._window_repo.insert(updated_window, conn)
                        else:
                            updated_window = await self._window_repo.update(updated_window, conn)

                        # Falls ein neues Fenster angelegt wurde, muss der Draw auf die echte,
                        # bereits persistierte window_id zeigen, bevor er gespeichert wird.
                        draw.window_id = updated_window.window_id

                    # Schritt 4: Draw schreiben
                    saved_draw = await self._draw_repo.insert(draw, conn)

                    effective_window = (
                        updated_window if updated_window is not None else active_window
                    )

                self._supervisor_state.record_draw_success(saved_draw)
                logger.info(
                    "Draw gespeichert: id=%s mode=%s request_id=%s",
                    saved_draw.id,
                    saved_draw.mode.value,
                    request.request_id,
                )
                if self._router_client is not None and saved_draw is not None:
                    router_result = await self._router_client.observe_draw(
                        saved_draw,
                        effective_window,
                    )
                    self._supervisor_state.record_router_result(
                        enabled=router_result.enabled,
                        available=router_result.available,
                        probe_status=router_result.status,
                        probe_message=router_result.message,
                        probe_error=router_result.error,
                        assessment_status=(
                            router_result.assessment.status
                            if router_result.assessment else None
                        ),
                        assessment_message=(
                            router_result.assessment.message
                            if router_result.assessment else None
                        ),
                        assessment_findings=(
                            router_result.assessment.findings
                            if router_result.assessment else None
                        ),
                        assessment_recommendations=(
                            router_result.assessment.recommendations
                            if router_result.assessment else None
                        ),
                        assessment_confidence=(
                            router_result.assessment.confidence
                            if router_result.assessment else None
                        ),
                        assessment_source=(
                            router_result.assessment.source
                            if router_result.assessment else None
                        ),
                        assessment_at=(
                            router_result.assessment.observed_at
                            if router_result.assessment else None
                        ),
                    )
                return saved_draw
            except pg_errors.UniqueViolation as exc:
                constraint = _constraint_name(exc)
                if constraint == "uq_draws_request_id":
                    existing = await self._draw_repo.find_by_request_id(request.request_id)
                    if existing is not None:
                        self._supervisor_state.record_draw_success(existing)
                        logger.info(
                            "Idempotente Rückgabe nach Request-ID-Konflikt für request_id=%s",
                            request.request_id,
                        )
                        return existing
                if constraint == "uq_effective_draw_per_date":
                    existing = await self._draw_repo.find_effective_by_date(request.draw_date)
                    if existing is not None:
                        self._supervisor_state.record_draw_success(existing)
                        logger.info(
                            "Bestehender effektiver Draw für draw_date=%s zurückgegeben",
                            request.draw_date,
                        )
                        return existing
                if constraint == "uq_active_window" and attempt == 0:
                    logger.info(
                        "ACTIVE-Fenster-Konflikt erkannt; Draw-Vorgang wird einmal neu versucht"
                    )
                    continue
                self._supervisor_state.record_error(
                    "draw_service",
                    f"UniqueViolation({constraint or 'unknown'})",
                )
                raise
            except Exception as exc:
                self._supervisor_state.record_error("draw_service", str(exc))
                raise

        raise RuntimeError("Draw-Vorgang konnte nach Retry nicht abgeschlossen werden")

    async def _handle_pair(
        self,
        request:       DrawRequest,
        active_window: FairnessWindow | None,
        conn:          object,
    ) -> tuple[Draw, FairnessWindow | None]:
        """
        PAIR-Logik mit AB/BA-Rotation.
        Liest den letzten PAIR-Draw für diesen pair_key, um cycle_index zu bestimmen.
        """
        # Letzten PAIR-Draw für diesen pair_key lesen
        last_pair_draw = await self._draw_repo.find_last_pair_for_key(
            _pair_key_for_mask(request.present_mask), conn
        )

        pair_cycle_index = None
        pair_last_full_order = None
        latest_effective_draw = None
        source_window_id = active_window.window_id if active_window else None
        source_window_index = active_window.window_index if active_window else None

        if last_pair_draw is None:
            pair_last_full_order = (
                active_window.last_full_order
                if active_window is not None and active_window.last_full_order is not None
                else None
            )
            if pair_last_full_order is None:
                latest_effective_draw = await self._draw_repo.find_latest_effective_draw()
                if (
                    latest_effective_draw is not None
                    and latest_effective_draw.mode == DrawMode.TRIPLET
                    and latest_effective_draw.perm_code is not None
                ):
                    pair_last_full_order = latest_effective_draw.perm_code
                    source_window_id = latest_effective_draw.window_id
                    source_window_index = latest_effective_draw.window_index
        else:
            last_cycle  = last_pair_draw.pair_cycle_index
            pair_cycle_index = next_pair_cycle_index(last_cycle)

        context = DrawContext.from_request(
            request,
            active_window,
            latest_effective_draw=latest_effective_draw,
            last_pair_draw=last_pair_draw,
            pair_cycle_index=pair_cycle_index,
            pair_last_full_order=pair_last_full_order,
            pair_window_id=source_window_id,
            pair_window_index=source_window_index,
        )
        draw, _ = build_draw_from_context(context)
        return draw, None


def _constraint_name(exc: BaseException) -> str | None:
    diag = getattr(exc, "diag", None)
    return getattr(diag, "constraint_name", None)
