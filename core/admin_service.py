"""
core/admin_service.py
Kleine Admin-Schicht fuer Dashboard, Listenansichten und manuelle Aktionen.
"""
from __future__ import annotations

import asyncio
import json
import shutil
from dataclasses import asdict, dataclass
from datetime import datetime, timezone
from pathlib import Path
from uuid import uuid4

from config.settings import Settings
from config.time import today_in_timezone
from core.draw_service import DrawService
from core.models import Draw, DrawRequest, FairnessWindow
from core.supervisor_service import SupervisorService
from integrations.router_client import RouterClient, RouterProbeResult
from persistence.repositories import DrawRepository, WindowRepository


@dataclass(slots=True)
class AdminActionResult:
    ok: bool
    title: str
    detail: str


class AdminService:
    def __init__(
        self,
        settings: Settings,
        supervisor_service: SupervisorService,
        draw_service: DrawService,
        draw_repo: DrawRepository,
        window_repo: WindowRepository,
        router_client: RouterClient,
    ) -> None:
        self._settings = settings
        self._supervisor_service = supervisor_service
        self._draw_service = draw_service
        self._draw_repo = draw_repo
        self._window_repo = window_repo
        self._router_client = router_client

    async def overview(self) -> dict[str, object]:
        status = await self._supervisor_service.snapshot()
        recent_draws = await self._draw_repo.list_recent(limit=10)
        recent_windows = await self._window_repo.list_recent(limit=10)
        return {
            "status": status,
            "recent_draws": recent_draws,
            "recent_windows": recent_windows,
            "config": self.config_snapshot(),
        }

    async def recent_draws(self, limit: int = 50) -> list[Draw]:
        return await self._draw_repo.list_recent(limit=limit)

    async def recent_windows(self, limit: int = 50) -> list[FairnessWindow]:
        return await self._window_repo.list_recent(limit=limit)

    def config_snapshot(self) -> list[dict[str, object]]:
        return [
            {"key": "api_host", "value": self._settings.api_host, "editable": False},
            {"key": "api_port", "value": self._settings.api_port, "editable": False},
            {"key": "router_enabled", "value": self._settings.router_enabled, "editable": False},
            {"key": "router_url", "value": self._settings.router_url or "-", "editable": False},
            {
                "key": "router_api_key",
                "value": self._mask_secret(self._settings.router_api_key),
                "editable": False,
            },
            {
                "key": "router_timeout_seconds",
                "value": self._settings.router_timeout_seconds,
                "editable": False,
            },
            {
                "key": "admin_backup_dir",
                "value": self._settings.admin_backup_dir,
                "editable": False,
            },
        ]

    async def trigger_draw(
        self,
        *,
        leon_present: bool,
        emmi_present: bool,
        elsa_present: bool,
    ) -> tuple[AdminActionResult, Draw]:
        draw = await self._draw_service.execute(
            DrawRequest(
                leon_present=leon_present,
                emmi_present=emmi_present,
                elsa_present=elsa_present,
                request_id=uuid4(),
                draw_date=today_in_timezone(self._settings.controller_timezone),
            )
        )
        return (
            AdminActionResult(
                ok=True,
                title="Draw ausgefuehrt",
                detail=(
                    f"Draw {draw.id} fuer {draw.draw_date.isoformat()} "
                    f"im Modus {draw.mode.value} gespeichert."
                ),
            ),
            draw,
        )

    async def probe_router(self) -> tuple[AdminActionResult, RouterProbeResult]:
        result = await self._router_client.probe_health()
        detail = result.message or "Keine Detailmeldung"
        if result.error:
            detail = f"{detail} ({result.error})"
        return (
            AdminActionResult(
                ok=bool(result.available),
                title="Router-Probe",
                detail=detail,
            ),
            result,
        )

    async def create_backup(self) -> AdminActionResult:
        backup_dir = Path(self._settings.admin_backup_dir)
        timestamp = datetime.now(tz=timezone.utc).strftime("%Y%m%d_%H%M%S")
        target = backup_dir / f"backup_{timestamp}"
        await asyncio.to_thread(self._create_backup_sync, backup_dir, target)
        return AdminActionResult(
            ok=True,
            title="Backup erstellt",
            detail=f"App-Backup unter {target}",
        )

    @staticmethod
    def _mask_secret(value: str | None) -> str:
        if not value:
            return "-"
        if len(value) <= 6:
            return "*" * len(value)
        return f"{value[:3]}***{value[-3:]}"

    @staticmethod
    def _create_backup_sync(backup_dir: Path, target: Path) -> None:
        backup_dir.mkdir(parents=True, exist_ok=True)
        shutil.copytree("/opt/kids_controller", target)
        manifest = {
            "created_at": datetime.now(tz=timezone.utc).isoformat(),
            "source": "/opt/kids_controller",
        }
        (target / "backup_manifest.json").write_text(
            json.dumps(manifest, indent=2),
            encoding="utf-8",
        )
