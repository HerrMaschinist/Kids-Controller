"""
config/time.py
Hilfsfunktionen für den fachlichen Tagesbezug des Kids Controllers.
"""
from __future__ import annotations

from datetime import date, datetime, timezone
from zoneinfo import ZoneInfo


def today_in_timezone(timezone_name: str, now: datetime | None = None) -> date:
    """
    Liefert das aktuelle Datum in der fachlich relevanten Zeitzone.

    Wenn `now` nicht übergeben wird, wird ein UTC-Zeitpunkt verwendet und dann
    in die Zielzeitzone konvertiert.
    """
    current = now or datetime.now(tz=timezone.utc)
    return current.astimezone(ZoneInfo(timezone_name)).date()
