"""
config/settings.py
Anwendungskonfiguration via Pydantic-Settings (Umgebungsvariablen oder .env).
"""
from __future__ import annotations

from pathlib import Path
from urllib.parse import urlparse

from pydantic import field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file="/etc/kids_controller/.env",
        env_file_encoding="utf-8",
        case_sensitive=False,
    )

    # Datenbankverbindung
    db_host: str = "192.168.50.10"
    db_port: int = 5432
    db_name: str = "kids_controller"
    db_user: str = "kids_controller_admin"
    db_password: str = "kc_secure_pw_change_me"
    db_min_connections: int = 2
    db_max_connections: int = 10

    # Algorithmus
    algorithm_version: str = "1.0.0"
    shuffle_algorithm: str = "fisher_yates"
    window_size: int = 12

    # API
    api_host: str = "0.0.0.0"
    api_port: int = 8001
    api_prefix: str = "/api/v1"
    debug: bool = False

    # Optionaler Supervisor-/Router-Pfad
    router_enabled: bool = False
    router_url: str | None = None
    router_api_key: str | None = None
    router_timeout_seconds: float = 2.0
    router_observe_path: str = "/route"

    # Admin-Oberfläche
    admin_enabled: bool = False
    admin_username: str | None = None
    admin_password: str | None = None
    admin_backup_dir: str = "/home/alex/backups/kids_controller_manual"

    @field_validator("router_url")
    @classmethod
    def validate_router_url(cls, value: str | None) -> str | None:
        if value is None:
            return None
        parsed = urlparse(value)
        if parsed.scheme not in {"http", "https"}:
            raise ValueError("router_url muss mit http:// oder https:// beginnen")
        if not parsed.netloc:
            raise ValueError("router_url muss einen Host enthalten")
        if parsed.path not in {"", "/"} or parsed.params or parsed.query or parsed.fragment:
            raise ValueError("router_url darf nur die Basis-URL ohne Pfad enthalten")
        return value.rstrip("/")

    @field_validator("router_observe_path")
    @classmethod
    def validate_router_observe_path(cls, value: str) -> str:
        if not value.startswith("/"):
            raise ValueError("router_observe_path muss mit / beginnen")
        if "//" in value or ".." in value or "?" in value or "#" in value:
            raise ValueError("router_observe_path enthält unzulässige Zeichen")
        return value

    @field_validator("router_timeout_seconds")
    @classmethod
    def validate_router_timeout(cls, value: float) -> float:
        if value <= 0 or value > 10:
            raise ValueError("router_timeout_seconds muss zwischen 0 und 10 Sekunden liegen")
        return value

    @field_validator("admin_username", "admin_password")
    @classmethod
    def validate_admin_credentials(cls, value: str | None) -> str | None:
        if value is None:
            return None
        value = value.strip()
        return value or None

    @field_validator("admin_backup_dir")
    @classmethod
    def validate_admin_backup_dir(cls, value: str) -> str:
        path = Path(value).expanduser()
        if not path.is_absolute():
            raise ValueError("admin_backup_dir muss ein absoluter Pfad sein")
        return str(path)

    @property
    def db_conninfo(self) -> str:
        """psycopg v3 conninfo-String."""
        return (
            f"host={self.db_host} port={self.db_port} "
            f"dbname={self.db_name} user={self.db_user} "
            f"password={self.db_password}"
        )


_settings: Settings | None = None


def get_settings() -> Settings:
    global _settings
    if _settings is None:
        _settings = Settings()
    return _settings
