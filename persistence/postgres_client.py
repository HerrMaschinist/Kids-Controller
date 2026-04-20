"""
persistence/postgres_client.py
Direkte psycopg v3 Async-Verbindung ohne Pool für KIDS_CONTROLLER.
Robuster für den aktuellen Stand und ausreichend für den privaten Einsatz.
"""
from __future__ import annotations

from config.settings import Settings, get_settings

_conninfo: str | None = None


async def create_pool(settings: Settings) -> str:
    global _conninfo
    _conninfo = settings.db_conninfo
    return _conninfo


async def close_pool() -> None:
    global _conninfo
    _conninfo = None


def get_pool() -> str:
    global _conninfo
    if _conninfo is None:
        _conninfo = get_settings().db_conninfo
    return _conninfo
