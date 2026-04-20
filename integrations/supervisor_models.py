"""
integrations/supervisor_models.py
Antwortschema für den internen Supervisor-/Status-Endpunkt.
"""
from __future__ import annotations

from datetime import date, datetime
from typing import Optional

from pydantic import BaseModel, Field


class SupervisorRouterStatus(BaseModel):
    enabled: bool
    available: Optional[bool] = None
    last_checked_at: Optional[datetime] = None
    last_probe_status: Optional[str] = None
    last_probe_message: Optional[str] = None
    last_probe_error: Optional[str] = None
    last_assessment_status: Optional[str] = None
    last_assessment_message: Optional[str] = None
    last_assessment_findings: list[str] = Field(default_factory=list)
    last_assessment_recommendations: list[str] = Field(default_factory=list)
    last_assessment_confidence: Optional[int] = None
    last_assessment_source: Optional[str] = None
    last_assessment_at: Optional[datetime] = None


class SupervisorInvariants(BaseModel):
    exactly_one_active_window: bool = False
    active_window_present: bool = False
    latest_effective_draw_present: bool = False
    last_error_present: bool = False


class SupervisorStatusResponse(BaseModel):
    status: str = "ok"
    active_window_id: Optional[str] = None
    active_window_status: Optional[str] = None
    active_window_index: Optional[int] = None
    last_successful_draw_id: Optional[int] = None
    last_successful_draw_date: Optional[date] = None
    last_successful_draw_mode: Optional[str] = None
    last_successful_draw_generated_at: Optional[datetime] = None
    last_run_at: Optional[datetime] = None
    last_error_at: Optional[datetime] = None
    last_error_source: Optional[str] = None
    last_error_message: Optional[str] = None
    router: SupervisorRouterStatus = Field(default_factory=lambda: SupervisorRouterStatus(enabled=False))
    invariants: SupervisorInvariants = Field(default_factory=SupervisorInvariants)
