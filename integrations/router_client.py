"""
integrations/router_client.py
Optionaler, harmloser Beobachtungsclient für den lokalen Router.

Der Client beeinflusst den Draw nicht. Er meldet nur Beobachtungen an einen
konfigurierten Router und protokolliert dessen Bewertung.
"""
from __future__ import annotations

import hashlib
import json
import logging
from dataclasses import dataclass
from urllib.parse import urljoin
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen

from config.settings import Settings
from core.models import Draw, FairnessWindow
from integrations.router_models import (
    RouterAssessment,
    RouterDrawObservation,
    RouterRouteRequest,
    RouterRouteResponse,
)

logger = logging.getLogger(__name__)


@dataclass(slots=True)
class RouterProbeResult:
    enabled: bool
    available: bool | None
    status: str | None
    message: str | None
    error: str | None
    status_code: int | None
    assessment: RouterAssessment | None


class RouterClient:
    def __init__(self, settings: Settings) -> None:
        self._enabled = settings.router_enabled and bool(settings.router_url)
        self._base_url = settings.router_url.rstrip("/") if settings.router_url else None
        self._api_key = settings.router_api_key.strip() if settings.router_api_key else None
        self._timeout_seconds = settings.router_timeout_seconds
        self._route_path = settings.router_observe_path

    @property
    def enabled(self) -> bool:
        return self._enabled

    async def probe_health(self) -> RouterProbeResult:
        if not self._enabled or not self._base_url:
            return RouterProbeResult(
                enabled=False,
                available=None,
                status="disabled",
                message="Router ist deaktiviert oder nicht konfiguriert",
                error=None,
                status_code=None,
                assessment=None,
            )
        return self._get_health()

    async def observe_draw(
        self,
        draw: Draw,
        window: FairnessWindow | None,
    ) -> RouterProbeResult:
        if not self._enabled or not self._base_url:
            return RouterProbeResult(
                enabled=False,
                available=None,
                status="disabled",
                message="Router ist deaktiviert oder nicht konfiguriert",
                error=None,
                status_code=None,
                assessment=None,
            )

        observation = RouterDrawObservation(
            draw_id=draw.id,
            draw_date=draw.draw_date,
            mode=draw.mode,
            present_mask=draw.present_mask,
            window_id=draw.window_id,
            window_index=draw.window_index,
            active_window_index_snapshot=draw.active_window_index_snapshot,
            window_status=window.window_status if window else None,
            last_window_mode=window.last_mode if window and window.last_mode else None,
            perm_code=draw.perm_code,
            derived_from_last_full_order=draw.derived_from_last_full_order,
            is_effective=draw.is_effective,
            pair_key=draw.pair_key,
            pair_cycle_index=draw.pair_cycle_index,
            pos1=draw.pos1,
            pos2=draw.pos2,
            pos3=draw.pos3,
            stop_morning=draw.stop_morning,
            stop_midday=draw.stop_midday,
            observation_fingerprint=self._fingerprint_observation(draw, window),
            latest_effective_draw_id=draw.id,
            latest_effective_draw_fingerprint=self._fingerprint_effective_draw(draw),
        )
        route_request = RouterRouteRequest(
            prompt=(
                "Bewerte die folgende Kids_Controller-Beobachtung streng "
                "supervisorisch. Antworte ausschließlich als JSON mit den Feldern "
                "status, message, findings, recommendations, confidence, source "
                "und observed_at. Nutze ausschließlich die Beobachtungsdaten; "
                "keine freien Ergänzungen.\n\n"
                f"{json.dumps({'kind': 'kids_controller_observation', 'observation': observation.model_dump(mode='json')}, separators=(',', ':'))}"
            ),
            stream=False,
        )

        try:
            return self._post_observation(route_request)
        except (HTTPError, URLError, TimeoutError, json.JSONDecodeError, ValueError) as exc:
            logger.warning("Router-Beobachtung fehlgeschlagen: %s", exc.__class__.__name__)
            return RouterProbeResult(
                enabled=True,
                available=False,
                status="degraded",
                message="Router-Beobachtung fehlgeschlagen",
                error=exc.__class__.__name__,
                status_code=None,
                assessment=None,
            )
        except Exception as exc:  # pragma: no cover - defensive fallback
            logger.warning("Router-Beobachtung unerwartet fehlgeschlagen: %s", exc.__class__.__name__)
            return RouterProbeResult(
                enabled=True,
                available=False,
                status="degraded",
                message="Router-Beobachtung fehlgeschlagen",
                error="unexpected_error",
                status_code=None,
                assessment=None,
            )

    def _post_observation(
        self,
        request_payload: RouterRouteRequest,
    ) -> RouterProbeResult:
        assert self._base_url is not None
        url = f"{self._base_url}{self._route_path}"
        payload = request_payload.model_dump(mode="json")
        headers = {"Content-Type": "application/json"}
        if self._api_key:
            headers["X-API-Key"] = self._api_key
        request = Request(
            url,
            data=json.dumps(payload).encode("utf-8"),
            headers=headers,
            method="POST",
        )

        try:
            with urlopen(request, timeout=self._timeout_seconds) as response:
                body = response.read().decode("utf-8").strip()
                if not body:
                    raise ValueError("Router-Response ohne Body")
                parsed = json.loads(body)
                if not isinstance(parsed, dict):
                    raise ValueError("Router-Response ist kein JSON-Objekt")
                route_response = RouterRouteResponse.model_validate(parsed)
                assessment_payload = json.loads(route_response.response)
                if not isinstance(assessment_payload, dict):
                    raise ValueError("Router-Response enthält keine JSON-Bewertung")
                assessment = RouterAssessment.model_validate(assessment_payload)
                return RouterProbeResult(
                    enabled=True,
                    available=True,
                    status=assessment.status,
                    message=assessment.message,
                    error=None,
                    status_code=getattr(response, "status", None),
                    assessment=assessment,
                )
        except HTTPError as exc:
            return RouterProbeResult(
                enabled=True,
                available=False,
                status="degraded",
                message="Router meldete einen HTTP-Fehler",
                error=f"HTTP {getattr(exc, 'code', 'unknown')}",
                status_code=getattr(exc, "code", None),
                assessment=None,
            )
        except TimeoutError:
            return RouterProbeResult(
                enabled=True,
                available=False,
                status="degraded",
                message="Router-Anfrage timeout",
                error="timeout",
                status_code=None,
                assessment=None,
            )
        except URLError as exc:
            reason = getattr(exc, "reason", None)
            return RouterProbeResult(
                enabled=True,
                available=False,
                status="degraded",
                message="Router nicht erreichbar",
                error=reason.__class__.__name__ if reason is not None else "unreachable",
                status_code=None,
                assessment=None,
            )

    def _get_health(self) -> RouterProbeResult:
        assert self._base_url is not None
        url = urljoin(f"{self._base_url}/", "health")
        headers = {}
        if self._api_key:
            headers["X-API-Key"] = self._api_key
        request = Request(
            url,
            headers=headers,
            method="GET",
        )
        try:
            with urlopen(request, timeout=self._timeout_seconds) as response:
                body = response.read().decode("utf-8").strip()
                payload = json.loads(body) if body else {}
                status = payload.get("status", "ok") if isinstance(payload, dict) else "ok"
                service = payload.get("service") if isinstance(payload, dict) else None
                return RouterProbeResult(
                    enabled=True,
                    available=True,
                    status=str(status),
                    message=(
                        f"Router-Health erfolgreich ({service})"
                        if service else "Router-Health erfolgreich"
                    ),
                    error=None,
                    status_code=getattr(response, "status", None),
                    assessment=None,
                )
        except HTTPError as exc:
            return RouterProbeResult(
                enabled=True,
                available=False,
                status="degraded",
                message="Router-Health meldete einen HTTP-Fehler",
                error=f"HTTP {getattr(exc, 'code', 'unknown')}",
                status_code=getattr(exc, "code", None),
                assessment=None,
            )
        except TimeoutError:
            return RouterProbeResult(
                enabled=True,
                available=False,
                status="degraded",
                message="Router-Health timeout",
                error="timeout",
                status_code=None,
                assessment=None,
            )
        except URLError as exc:
            reason = getattr(exc, "reason", None)
            return RouterProbeResult(
                enabled=True,
                available=False,
                status="degraded",
                message="Router-Health nicht erreichbar",
                error=reason.__class__.__name__ if reason is not None else "unreachable",
                status_code=None,
                assessment=None,
            )
        except (json.JSONDecodeError, ValueError) as exc:
            return RouterProbeResult(
                enabled=True,
                available=False,
                status="degraded",
                message="Router-Health lieferte ungültige Antwort",
                error=exc.__class__.__name__,
                status_code=None,
                assessment=None,
            )

    @staticmethod
    def _fingerprint_observation(draw: Draw, window: FairnessWindow | None) -> str:
        parts = [
            f"draw:{draw.draw_date.isoformat()}",
            f"mode:{draw.mode.value}",
            f"mask:{draw.present_mask}",
            f"pos:{draw.pos1}:{draw.pos2}:{draw.pos3}",
            f"stop:{draw.stop_morning}:{draw.stop_midday}",
            f"window:{window.window_id if window else ''}",
            f"window_status:{window.window_status.value if window else ''}",
            f"window_index:{window.window_index if window else ''}",
            f"window_mode:{window.last_mode.value if window and window.last_mode else ''}",
        ]
        return hashlib.sha256("|".join(parts).encode("utf-8")).hexdigest()

    @staticmethod
    def _fingerprint_effective_draw(draw: Draw) -> str:
        parts = [
            f"id:{draw.id}",
            f"date:{draw.draw_date.isoformat()}",
            f"mode:{draw.mode.value}",
            f"mask:{draw.present_mask}",
            f"pos:{draw.pos1}:{draw.pos2}:{draw.pos3}",
            f"stop:{draw.stop_morning}:{draw.stop_midday}",
        ]
        return hashlib.sha256("|".join(parts).encode("utf-8")).hexdigest()
