"""
core/supervisor_state.py
Laufzeitstatus für Beobachtung, Fehler und optionalen Router-/Supervisorpfad.

Die Daten sind bewusst klein und in-memory gehalten, damit der deterministische
Draw-Pfad nicht von einer zusätzlichen Persistenz abhängig wird.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from datetime import date, datetime, timezone
from threading import Lock
from typing import Optional

from core.models import Draw


@dataclass(slots=True)
class RouterProbeState:
    enabled: bool = False
    available: Optional[bool] = None
    last_checked_at: Optional[datetime] = None
    last_probe_status: Optional[str] = None
    last_probe_message: Optional[str] = None
    last_probe_error: Optional[str] = None
    last_assessment_status: Optional[str] = None
    last_assessment_message: Optional[str] = None
    last_assessment_findings: list[str] = field(default_factory=list)
    last_assessment_recommendations: list[str] = field(default_factory=list)
    last_assessment_confidence: Optional[int] = None
    last_assessment_source: Optional[str] = None
    last_assessment_at: Optional[datetime] = None


@dataclass(slots=True)
class SupervisorSnapshot:
    last_run_at: Optional[datetime]
    last_successful_draw_id: Optional[int]
    last_successful_draw_date: Optional[date]
    last_successful_draw_mode: Optional[str]
    last_error_at: Optional[datetime]
    last_error_source: Optional[str]
    last_error_message: Optional[str]
    router: RouterProbeState


class SupervisorState:
    def __init__(self) -> None:
        self._lock = Lock()
        self._last_run_at: Optional[datetime] = None
        self._last_successful_draw_id: Optional[int] = None
        self._last_successful_draw_date: Optional[date] = None
        self._last_successful_draw_mode: Optional[str] = None
        self._last_error_at: Optional[datetime] = None
        self._last_error_source: Optional[str] = None
        self._last_error_message: Optional[str] = None
        self._router = RouterProbeState(
        )

    def record_draw_success(self, draw: Draw) -> None:
        with self._lock:
            self._last_run_at = draw.draw_ts.astimezone(timezone.utc)
            self._last_successful_draw_id = draw.id
            self._last_successful_draw_date = draw.draw_date
            self._last_successful_draw_mode = draw.mode.value
            self._last_error_at = None
            self._last_error_source = None
            self._last_error_message = None

    def record_error(self, source: str, message: str) -> None:
        with self._lock:
            self._last_error_at = datetime.now(tz=timezone.utc)
            self._last_error_source = source
            self._last_error_message = message

    def record_router_result(
        self,
        *,
        enabled: bool,
        available: Optional[bool],
        probe_status: Optional[str],
        probe_message: Optional[str],
        probe_error: Optional[str],
        assessment_status: Optional[str] = None,
        assessment_message: Optional[str] = None,
        assessment_findings: Optional[list[str]] = None,
        assessment_recommendations: Optional[list[str]] = None,
        assessment_confidence: Optional[int] = None,
        assessment_source: Optional[str] = None,
        assessment_at: Optional[datetime] = None,
    ) -> None:
        with self._lock:
            self._router.enabled = enabled
            self._router.available = available
            self._router.last_checked_at = datetime.now(tz=timezone.utc)
            self._router.last_probe_status = probe_status
            self._router.last_probe_message = probe_message
            self._router.last_probe_error = probe_error
            if assessment_status is not None:
                self._router.last_assessment_status = assessment_status
                self._router.last_assessment_message = assessment_message
                self._router.last_assessment_findings = list(assessment_findings or [])
                self._router.last_assessment_recommendations = list(
                    assessment_recommendations or []
                )
                self._router.last_assessment_confidence = assessment_confidence
                self._router.last_assessment_source = assessment_source
                self._router.last_assessment_at = assessment_at

    def snapshot(self) -> SupervisorSnapshot:
        with self._lock:
            return SupervisorSnapshot(
                last_run_at=self._last_run_at,
                last_successful_draw_id=self._last_successful_draw_id,
                last_successful_draw_date=self._last_successful_draw_date,
                last_successful_draw_mode=self._last_successful_draw_mode,
                last_error_at=self._last_error_at,
                last_error_source=self._last_error_source,
                last_error_message=self._last_error_message,
                router=RouterProbeState(
                    enabled=self._router.enabled,
                    available=self._router.available,
                    last_checked_at=self._router.last_checked_at,
                    last_probe_status=self._router.last_probe_status,
                    last_probe_message=self._router.last_probe_message,
                    last_probe_error=self._router.last_probe_error,
                    last_assessment_status=self._router.last_assessment_status,
                    last_assessment_message=self._router.last_assessment_message,
                    last_assessment_findings=list(self._router.last_assessment_findings or []),
                    last_assessment_recommendations=list(
                        self._router.last_assessment_recommendations or []
                    ),
                    last_assessment_confidence=self._router.last_assessment_confidence,
                    last_assessment_source=self._router.last_assessment_source,
                    last_assessment_at=self._router.last_assessment_at,
                ),
            )


_SUPERVISOR_STATE: SupervisorState | None = None


def get_supervisor_state() -> SupervisorState:
    global _SUPERVISOR_STATE
    if _SUPERVISOR_STATE is None:
        _SUPERVISOR_STATE = SupervisorState()
    return _SUPERVISOR_STATE
