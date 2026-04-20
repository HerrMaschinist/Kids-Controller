from __future__ import annotations

from urllib.error import URLError

import pytest
from fastapi.security import HTTPBasicCredentials

import config.settings as settings_module
from app.admin_routes import _checkbox_value, require_admin_auth
from integrations.router_client import RouterClient


def test_checkbox_value_handles_expected_inputs():
    assert _checkbox_value("on") is True
    assert _checkbox_value("true") is True
    assert _checkbox_value("yes") is True
    assert _checkbox_value(None) is False
    assert _checkbox_value("off") is False


def test_require_admin_auth_accepts_valid_credentials(monkeypatch):
    monkeypatch.setenv("ADMIN_ENABLED", "true")
    monkeypatch.setenv("ADMIN_USERNAME", "admin")
    monkeypatch.setenv("ADMIN_PASSWORD", "secret")
    settings_module._settings = None

    username = require_admin_auth(HTTPBasicCredentials(username="admin", password="secret"))

    assert username == "admin"
    settings_module._settings = None


def test_require_admin_auth_rejects_invalid_credentials(monkeypatch):
    monkeypatch.setenv("ADMIN_ENABLED", "true")
    monkeypatch.setenv("ADMIN_USERNAME", "admin")
    monkeypatch.setenv("ADMIN_PASSWORD", "secret")
    settings_module._settings = None

    with pytest.raises(Exception) as exc_info:
        require_admin_auth(HTTPBasicCredentials(username="admin", password="wrong"))

    assert getattr(exc_info.value, "status_code", None) == 401
    settings_module._settings = None


def test_router_probe_health_reports_reachable(monkeypatch):
    client = RouterClient(
        settings_module.Settings(
            router_enabled=True,
            router_url="http://router.local",
            router_api_key="secret-key",
            router_timeout_seconds=1.0,
        )
    )

    class _FakeResponse:
        status = 200

        def __enter__(self):
            return self

        def __exit__(self, exc_type, exc, tb):
            return False

        def read(self) -> bytes:
            return b'{"status":"ok","service":"pi_guardian_router"}'

    monkeypatch.setattr("integrations.router_client.urlopen", lambda request, timeout: _FakeResponse())

    result = __import__("asyncio").run(client.probe_health())

    assert result.available is True
    assert result.status == "ok"


def test_router_probe_health_reports_unreachable(monkeypatch):
    client = RouterClient(
        settings_module.Settings(
            router_enabled=True,
            router_url="http://router.local",
            router_api_key="secret-key",
            router_timeout_seconds=1.0,
        )
    )

    def _raise_urlerror(request, timeout):
        raise URLError("no route")

    monkeypatch.setattr("integrations.router_client.urlopen", _raise_urlerror)

    result = __import__("asyncio").run(client.probe_health())

    assert result.available is False
    assert result.status == "degraded"
