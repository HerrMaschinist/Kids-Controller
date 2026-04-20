"""
core/supervisor_service.py
Lesende Statusschicht für Betrieb und spätere Supervisor-Integration.
"""
from __future__ import annotations

from core.supervisor_state import SupervisorState
from integrations.supervisor_models import (
    SupervisorInvariants,
    SupervisorRouterStatus,
    SupervisorStatusResponse,
)
from persistence.repositories import DrawRepository, WindowRepository


class SupervisorService:
    def __init__(
        self,
        window_repo: WindowRepository,
        draw_repo: DrawRepository,
        supervisor_state: SupervisorState,
        router_enabled: bool = False,
    ) -> None:
        self._window_repo = window_repo
        self._draw_repo = draw_repo
        self._supervisor_state = supervisor_state
        self._router_enabled = router_enabled

    async def snapshot(self) -> SupervisorStatusResponse:
        active_count = await self._window_repo.count_active_windows()
        active_window = await self._window_repo.find_active()
        latest_draw = await self._draw_repo.find_latest_effective_draw()
        state = self._supervisor_state.snapshot()

        last_successful_draw_id = state.last_successful_draw_id
        last_successful_draw_date = state.last_successful_draw_date
        last_successful_draw_mode = state.last_successful_draw_mode
        last_successful_draw_generated_at = state.last_run_at
        last_run_at = state.last_run_at
        if latest_draw is not None:
            if last_successful_draw_id is None:
                last_successful_draw_id = latest_draw.id
            if last_successful_draw_date is None:
                last_successful_draw_date = latest_draw.draw_date
            if last_successful_draw_mode is None:
                last_successful_draw_mode = latest_draw.mode.value
            if last_successful_draw_generated_at is None:
                last_successful_draw_generated_at = latest_draw.draw_ts
            if last_run_at is None:
                last_run_at = latest_draw.draw_ts

        return SupervisorStatusResponse(
            active_window_id=active_window.window_id if active_window else None,
            active_window_status=active_window.window_status.value if active_window else None,
            active_window_index=active_window.window_index if active_window else None,
            last_successful_draw_id=last_successful_draw_id,
            last_successful_draw_date=last_successful_draw_date,
            last_successful_draw_mode=last_successful_draw_mode,
            last_successful_draw_generated_at=last_successful_draw_generated_at,
            last_run_at=last_run_at,
            last_error_at=state.last_error_at,
            last_error_source=state.last_error_source,
            last_error_message=state.last_error_message,
            router=SupervisorRouterStatus(
                enabled=state.router.enabled or self._router_enabled,
                available=state.router.available,
                last_checked_at=state.router.last_checked_at,
                last_probe_status=state.router.last_probe_status,
                last_probe_message=state.router.last_probe_message,
                last_probe_error=state.router.last_probe_error,
                last_assessment_status=state.router.last_assessment_status,
                last_assessment_message=state.router.last_assessment_message,
                last_assessment_findings=state.router.last_assessment_findings or [],
                last_assessment_recommendations=state.router.last_assessment_recommendations or [],
                last_assessment_confidence=state.router.last_assessment_confidence,
                last_assessment_source=state.router.last_assessment_source,
                last_assessment_at=state.router.last_assessment_at,
            ),
            invariants=SupervisorInvariants(
                exactly_one_active_window=active_count == 1,
                active_window_present=active_window is not None,
                latest_effective_draw_present=latest_draw is not None,
                last_error_present=state.last_error_at is not None,
            ),
        )
