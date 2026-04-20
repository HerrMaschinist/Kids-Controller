"""
app/dependencies.py
FastAPI Dependency Injection: Pool, Repositories, DrawService.
"""
from __future__ import annotations

from fastapi import Request

from core.draw_service import DrawService
from core.admin_service import AdminService
from core.supervisor_service import SupervisorService
from core.supervisor_state import get_supervisor_state
from config.settings import get_settings
from integrations.router_client import RouterClient
from persistence.postgres_client import get_pool
from persistence.repositories import DrawRepository, WindowRepository


def get_window_repository(request: Request) -> WindowRepository:
    return WindowRepository(get_pool())


def get_draw_repository(request: Request) -> DrawRepository:
    return DrawRepository(get_pool())


def get_draw_service(request: Request) -> DrawService:
    pool = get_pool()
    return DrawService(
        window_repo=WindowRepository(pool),
        draw_repo=DrawRepository(pool),
        router_client=get_router_client(),
        supervisor_state=get_supervisor_state(),
    )


def get_router_client() -> RouterClient:
    return RouterClient(get_settings())


def get_supervisor_service(request: Request) -> SupervisorService:
    pool = get_pool()
    settings = get_settings()
    return SupervisorService(
        window_repo=WindowRepository(pool),
        draw_repo=DrawRepository(pool),
        supervisor_state=get_supervisor_state(),
        router_enabled=settings.router_enabled and bool(settings.router_url),
    )


def get_admin_service(request: Request) -> AdminService:
    pool = get_pool()
    settings = get_settings()
    return AdminService(
        settings=settings,
        supervisor_service=SupervisorService(
            window_repo=WindowRepository(pool),
            draw_repo=DrawRepository(pool),
            supervisor_state=get_supervisor_state(),
            router_enabled=settings.router_enabled and bool(settings.router_url),
        ),
        draw_service=DrawService(
            window_repo=WindowRepository(pool),
            draw_repo=DrawRepository(pool),
            router_client=get_router_client(),
            supervisor_state=get_supervisor_state(),
        ),
        draw_repo=DrawRepository(pool),
        window_repo=WindowRepository(pool),
        router_client=get_router_client(),
    )
