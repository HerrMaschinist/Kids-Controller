from __future__ import annotations

import asyncio
import json
from urllib.error import HTTPError

from config.settings import Settings
from core.draw_service import DrawService
from core.supervisor_service import SupervisorService
from core.supervisor_state import SupervisorState
from core.models import DrawMode
from integrations.router_client import RouterClient
from integrations.router_models import RouterAssessment

from tests.test_draw_service import (
    FakeDrawRepo,
    FakeWindowRepo,
    _make_active_window,
    _make_request,
    _run,
)


class _FakeResponse:
    def __init__(self, status: int, body: dict[str, object]) -> None:
        self.status = status
        self._body = body

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc, tb):
        return False

    def read(self) -> bytes:
        return json.dumps(self._body).encode("utf-8")


class _FakeResponseText:
    def __init__(self, status: int, body: str) -> None:
        self.status = status
        self._body = body

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc, tb):
        return False

    def read(self) -> bytes:
        return self._body.encode("utf-8")


class _SnapshotWindowRepo:
    def __init__(self, active_window):
        self._active_window = active_window

    async def count_active_windows(self):
        return 1 if self._active_window is not None else 0

    async def find_active(self):
        return self._active_window


class _SnapshotDrawRepo(FakeDrawRepo):
    def __init__(self, draws):
        super().__init__()
        self.draws = list(draws)

    async def find_latest_effective_draw(self):
        for draw in reversed(self.draws):
            if draw.is_effective:
                return draw
        return None


def test_router_client_disabled_is_non_blocking():
    client = RouterClient(Settings(router_enabled=False, router_url=None))
    draw_repo = FakeDrawRepo()
    window = _make_active_window()
    draw = _run(
        DrawService(FakeWindowRepo(window), draw_repo, router_client=None).execute(
            _make_request(True, True, True)
        )
    )

    assert draw.mode == DrawMode.TRIPLET
    # Der Router ist deaktiviert, die Kernlogik bleibt unverändert.
    result = _run(client.observe_draw(draw, window))
    assert result.status == "disabled"
    assert result.available is None


def test_router_client_parses_assessment(monkeypatch):
    client = RouterClient(
        Settings(
            router_enabled=True,
            router_url="http://router.local",
            router_api_key="secret-key",
            router_timeout_seconds=1.0,
            router_observe_path="/route",
        )
    )
    draw_repo = FakeDrawRepo()
    window = _make_active_window()
    draw = _run(
        DrawService(FakeWindowRepo(window), draw_repo, router_client=None).execute(
            _make_request(True, True, True)
        )
    )

    captured = {}

    def _fake_urlopen(request, timeout):
        captured["url"] = request.full_url
        headers = dict(request.header_items())
        captured["headers"] = headers
        captured["body"] = json.loads(request.data.decode())
        assert any(
            key.lower() == "x-api-key" and value == "secret-key"
            for key, value in headers.items()
        )
        assert request.full_url.endswith("/route")
        return _FakeResponse(
            200,
            {
                "request_id": "rid-1",
                "model": "qwen2.5-coder:1.5b",
                "response": json.dumps(
                    {
                        "status": "warning",
                        "message": "Plausibilitätswarnung",
                        "findings": ["inactive-window"],
                        "recommendations": ["check-window-state"],
                        "confidence": 80,
                        "source": "router",
                    }
                ),
                "done": True,
                "done_reason": "stop",
                "duration_ms": 12,
            },
        )

    monkeypatch.setattr("integrations.router_client.urlopen", _fake_urlopen)

    result = _run(client.observe_draw(draw, window))

    assert result.available is True
    assert result.status == "warning"
    assert isinstance(result.assessment, RouterAssessment)
    assert result.assessment.findings == ["inactive-window"]
    assert "Bewerte die folgende Kids_Controller-Beobachtung" in captured["body"]["prompt"]
    assert captured["body"]["preferred_model"] is None
    assert captured["body"]["stream"] is False


def test_router_timeout_degrades_without_changing_core(monkeypatch):
    client = RouterClient(
        Settings(
            router_enabled=True,
            router_url="http://router.local",
            router_api_key="secret-key",
            router_timeout_seconds=1.0,
            router_observe_path="/route",
        )
    )
    window = _make_active_window()
    draw = _run(
        DrawService(FakeWindowRepo(window), FakeDrawRepo(), router_client=None).execute(
            _make_request(True, True, True)
        )
    )

    def _raise_timeout(request, timeout):
        raise TimeoutError("timed out")

    monkeypatch.setattr("integrations.router_client.urlopen", _raise_timeout)
    result = _run(client.observe_draw(draw, window))

    assert result.available is False
    assert result.status == "degraded"
    assert result.error == "timeout"


def test_router_invalid_json_degrades(monkeypatch):
    client = RouterClient(
        Settings(
            router_enabled=True,
            router_url="http://router.local",
            router_api_key="secret-key",
            router_timeout_seconds=1.0,
            router_observe_path="/route",
        )
    )
    window = _make_active_window()
    draw = _run(
        DrawService(FakeWindowRepo(window), FakeDrawRepo(), router_client=None).execute(
            _make_request(True, True, True)
        )
    )

    monkeypatch.setattr(
        "integrations.router_client.urlopen",
        lambda request, timeout: _FakeResponseText(200, "not-json"),
    )
    result = _run(client.observe_draw(draw, window))

    assert result.available is False
    assert result.status == "degraded"
    assert result.error == "JSONDecodeError"


def test_router_wrong_structure_degrades(monkeypatch):
    client = RouterClient(
        Settings(
            router_enabled=True,
            router_url="http://router.local",
            router_api_key="secret-key",
            router_timeout_seconds=1.0,
            router_observe_path="/route",
        )
    )
    window = _make_active_window()
    draw = _run(
        DrawService(FakeWindowRepo(window), FakeDrawRepo(), router_client=None).execute(
            _make_request(True, True, True)
        )
    )

    monkeypatch.setattr(
        "integrations.router_client.urlopen",
        lambda request, timeout: _FakeResponse(
            200,
            {
                "status": "warning",
                "message": "ok",
                "findings": ["x"],
                "recommendations": [],
                "confidence": 50,
                "source": "router",
                "unexpected": "field",
            },
        ),
    )
    result = _run(client.observe_draw(draw, window))

    assert result.available is False
    assert result.status == "degraded"
    assert result.error == "ValidationError"


def test_router_missing_api_key_degrades(monkeypatch):
    client = RouterClient(
        Settings(
            router_enabled=True,
            router_url="http://router.local",
            router_api_key=None,
            router_timeout_seconds=1.0,
            router_observe_path="/route",
        )
    )
    window = _make_active_window()
    draw = _run(
        DrawService(FakeWindowRepo(window), FakeDrawRepo(), router_client=None).execute(
            _make_request(True, True, True)
        )
    )

    def _unauthorized(request, timeout):
        headers = dict(request.header_items())
        assert not any(key.lower() == "x-api-key" for key in headers)
        raise HTTPError(request.full_url, 401, "Unauthorized", hdrs=None, fp=None)

    monkeypatch.setattr("integrations.router_client.urlopen", _unauthorized)
    result = _run(client.observe_draw(draw, window))

    assert result.available is False
    assert result.status == "degraded"
    assert result.error == "HTTP 401"


def test_router_wrong_api_key_degrades(monkeypatch):
    client = RouterClient(
        Settings(
            router_enabled=True,
            router_url="http://router.local",
            router_api_key="wrong-key",
            router_timeout_seconds=1.0,
            router_observe_path="/route",
        )
    )
    window = _make_active_window()
    draw = _run(
        DrawService(FakeWindowRepo(window), FakeDrawRepo(), router_client=None).execute(
            _make_request(True, True, True)
        )
    )

    def _forbidden(request, timeout):
        headers = dict(request.header_items())
        assert any(
            key.lower() == "x-api-key" and value == "wrong-key"
            for key, value in headers.items()
        )
        raise HTTPError(request.full_url, 403, "Forbidden", hdrs=None, fp=None)

    monkeypatch.setattr("integrations.router_client.urlopen", _forbidden)
    result = _run(client.observe_draw(draw, window))

    assert result.available is False
    assert result.status == "degraded"
    assert result.error == "HTTP 403"


def test_supervisor_snapshot_reports_status():
    window_repo = FakeWindowRepo(_make_active_window())
    draw_repo = FakeDrawRepo()
    state = SupervisorState()
    draw_service = DrawService(window_repo, draw_repo, router_client=None, supervisor_state=state)

    _run(draw_service.execute(_make_request(True, True, True)))

    supervisor = SupervisorService(
        _SnapshotWindowRepo(window_repo.active_window),
        _SnapshotDrawRepo(draw_repo.draws),
        state,
    )
    snapshot = _run(supervisor.snapshot())

    assert snapshot.active_window_id == "ABCD1234"
    assert snapshot.invariants.exactly_one_active_window is True
    assert snapshot.invariants.active_window_present is True
    assert snapshot.invariants.latest_effective_draw_present is True
    assert snapshot.last_successful_draw_mode == "TRIPLET"
    assert snapshot.invariants.last_error_present is False


def test_status_reflects_router_configuration_before_probe():
    window_repo = FakeWindowRepo(_make_active_window())
    draw_repo = FakeDrawRepo()
    state = SupervisorState()

    supervisor = SupervisorService(
        _SnapshotWindowRepo(window_repo.active_window),
        _SnapshotDrawRepo(draw_repo.draws),
        state,
        router_enabled=True,
    )
    snapshot = _run(supervisor.snapshot())

    assert snapshot.router.enabled is True
    assert snapshot.router.available is None
    assert snapshot.router.last_checked_at is None


def test_status_reflects_router_error_after_probe(monkeypatch):
    window = _make_active_window()
    window_repo = FakeWindowRepo(window)
    draw_repo = FakeDrawRepo()
    router_client = RouterClient(
        Settings(
            router_enabled=True,
            router_url="http://router.local",
            router_api_key="secret-key",
            router_timeout_seconds=1.0,
            router_observe_path="/route",
        )
    )
    state = SupervisorState()
    draw_service = DrawService(
        window_repo,
        draw_repo,
        router_client=router_client,
        supervisor_state=state,
    )

    monkeypatch.setattr(
        "integrations.router_client.urlopen",
        lambda request, timeout: _FakeResponseText(200, "not-json"),
    )

    _run(draw_service.execute(_make_request(True, True, True)))
    supervisor = SupervisorService(
        _SnapshotWindowRepo(window_repo.active_window),
        _SnapshotDrawRepo(draw_repo.draws),
        state,
    )
    snapshot = _run(supervisor.snapshot())

    assert snapshot.router.enabled is True
    assert snapshot.router.available is False
    assert snapshot.router.last_probe_status == "degraded"
    assert snapshot.router.last_probe_error == "JSONDecodeError"
    assert snapshot.last_successful_draw_mode == "TRIPLET"


def test_router_failure_keeps_last_valid_assessment(monkeypatch):
    window = _make_active_window()
    window_repo = FakeWindowRepo(window)
    draw_repo = FakeDrawRepo()
    router_client = RouterClient(
        Settings(
            router_enabled=True,
            router_url="http://router.local",
            router_api_key="secret-key",
            router_timeout_seconds=1.0,
            router_observe_path="/route",
        )
    )
    state = SupervisorState()
    draw_service = DrawService(
        window_repo,
        draw_repo,
        router_client=router_client,
        supervisor_state=state,
    )

    monkeypatch.setattr(
        "integrations.router_client.urlopen",
        lambda request, timeout: _FakeResponse(
            200,
            {
                "request_id": "rid-2",
                "model": "qwen2.5-coder:1.5b",
                "response": json.dumps(
                    {
                        "status": "recommend_review",
                        "message": "Bitte prüfen",
                        "findings": ["cycle-anomaly"],
                        "recommendations": ["review-window"],
                        "confidence": 90,
                        "source": "router",
                    }
                ),
                "done": True,
                "done_reason": "stop",
                "duration_ms": 11,
            },
        ),
    )

    _run(draw_service.execute(_make_request(True, True, True)))

    monkeypatch.setattr(
        "integrations.router_client.urlopen",
        lambda request, timeout: _FakeResponseText(200, "not-json"),
    )

    _run(draw_service.execute(_make_request(True, True, False)))

    supervisor = SupervisorService(
        _SnapshotWindowRepo(window_repo.active_window),
        _SnapshotDrawRepo(draw_repo.draws),
        state,
    )
    snapshot = _run(supervisor.snapshot())

    assert snapshot.router.last_assessment_status == "recommend_review"
    assert snapshot.router.last_assessment_findings == ["cycle-anomaly"]
    assert snapshot.router.last_probe_status == "degraded"
