"""
app/main.py
FastAPI-Anwendungseinstieg für KIDS_CONTROLLER.
Startet den psycopg v3 Connection-Pool, registriert den Router.
"""
from __future__ import annotations

from contextlib import asynccontextmanager
from typing import AsyncGenerator

from fastapi import FastAPI

from app.api_routes import router
from config.logging import configure_logging
from config.settings import get_settings
from persistence.postgres_client import close_pool, create_pool


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
    app.include_router(router)
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
