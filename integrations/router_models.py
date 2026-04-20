"""
integrations/router_models.py
Schema für die optionale Router-/Supervisor-Anbindung.
"""
from __future__ import annotations

from datetime import date, datetime, timezone
from typing import Any, Literal, Optional

from pydantic import BaseModel, ConfigDict, Field, field_validator

from core.models import DrawMode, PairKey, PermCode, WindowStatus


class RouterRouteRequest(BaseModel):
    prompt: str = Field(min_length=1, max_length=4000)
    preferred_model: Optional[str] = None
    stream: bool = False

    model_config = ConfigDict(extra="forbid", strict=True)


class RouterRouteResponse(BaseModel):
    request_id: str
    model: str
    response: str
    done: bool
    done_reason: str | None = None
    duration_ms: int

    model_config = ConfigDict(extra="forbid", strict=True)


class RouterDrawObservation(BaseModel):
    draw_id: int
    draw_date: date
    mode: DrawMode
    present_mask: int
    window_id: Optional[str] = None
    window_index: Optional[int] = None
    active_window_index_snapshot: Optional[int] = None
    window_status: Optional[WindowStatus] = None
    last_window_mode: Optional[DrawMode] = None
    perm_code: Optional[PermCode] = None
    derived_from_last_full_order: bool
    is_effective: bool
    pair_key: Optional[PairKey] = None
    pair_cycle_index: Optional[int] = None
    pos1: Optional[int] = None
    pos2: Optional[int] = None
    pos3: Optional[int] = None
    stop_morning: Optional[int] = None
    stop_midday: Optional[int] = None
    observation_fingerprint: str
    latest_effective_draw_id: Optional[int] = None
    latest_effective_draw_fingerprint: Optional[str] = None
    observed_at: datetime = Field(default_factory=lambda: datetime.now(tz=timezone.utc))

    model_config = ConfigDict(extra="forbid", strict=True)


class RouterAssessment(BaseModel):
    status: Literal[
        "ok",
        "warning",
        "anomaly_detected",
        "invariant_suspected",
        "recommend_review",
    ]
    message: str
    findings: list[str] = Field(default_factory=list)
    recommendations: list[str] = Field(default_factory=list)
    confidence: Optional[int] = Field(default=None, ge=0, le=100)
    source: Optional[str] = None
    observed_at: Optional[datetime] = None

    model_config = ConfigDict(extra="forbid", strict=True)
