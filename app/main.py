"""
app/main.py
FastAPI-Anwendungseinstieg für KIDS_CONTROLLER.
Startet den psycopg v3 Connection-Pool, registriert den Router.
"""
from __future__ import annotations

from contextlib import asynccontextmanager
from typing import AsyncGenerator

from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles

from app.admin_routes import api_router as admin_api_router
from app.admin_routes import router as admin_router
from app.api_routes import router
from config.logging import configure_logging
from config.settings import get_settings
from persistence.postgres_client import close_pool, create_pool
from pathlib import Path


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncGenerator[None, None]:
    settings = get_settings()
    configure_logging(debug=settings.debug)
    await create_pool(settings)
    yield
    await close_pool()


def create_app() -> FastAPI:
    app = FastAPI(
        title="KIDS_CONTROLLER",
        description="Faire Reihenfolgeberechnung für Leon, Emmi und Elsa",
        version="1.0.0",
        lifespan=lifespan,
    )
    frontend_dist = Path(__file__).resolve().parents[1] / "frontend" / "dist"
    app.mount(
        "/admin-assets",
        StaticFiles(directory=str(frontend_dist), check_dir=False),
        name="admin_assets",
    )
    app.include_router(router)
    app.include_router(admin_router)
    app.include_router(admin_api_router)
    return app


app = create_app()


if __name__ == "__main__":
    import uvicorn
    settings = get_settings()
    uvicorn.run(
        "app.main:app",
        host=settings.api_host,
        port=settings.api_port,
        reload=settings.debug,
    )
