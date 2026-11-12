"""Utilidades de fecha/hora compartidas.

Las fechas se guardan en UTC. Bolivia es UTC-4 todo el año (sin horario de verano),
por eso basta un offset fijo para calcular el inicio del día local.
"""
from datetime import datetime, timedelta, timezone

BOLIVIA_OFFSET = timedelta(hours=4)
BOLIVIA_TZ_NAME = "America/La_Paz"

# Una estación se considera "activa" si su último dato tiene menos de esta antigüedad
STATION_ACTIVE_WINDOW = timedelta(hours=1)


def utcnow() -> datetime:
    return datetime.now(timezone.utc)


def ensure_aware(dt: datetime) -> datetime:
    """Trata un datetime naive como UTC."""
    return dt.replace(tzinfo=timezone.utc) if dt.tzinfo is None else dt


def inicio_dia_bolivia(now: datetime) -> datetime:
    """Inicio del día actual en hora Bolivia (00:00 -04), expresado en UTC."""
    local = now - BOLIVIA_OFFSET
    return datetime(local.year, local.month, local.day, tzinfo=timezone.utc) + BOLIVIA_OFFSET
