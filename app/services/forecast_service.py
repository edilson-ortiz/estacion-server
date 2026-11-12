"""Pronóstico diario y por tramos desde el servicio propio pronostico.iagro360."""
from typing import Any

from app.core.config import settings
from app.core.http import TTLCache, get_http_client

_cache = TTLCache(settings.FORECAST_CACHE_TTL_SECONDS)


async def get_forecast_tramos(lat: float, lon: float) -> dict[str, Any]:
    """Devuelve {"daily": [...], "tramo": [...]} tal como lo entrega el servicio."""

    async def fetch() -> dict[str, Any]:
        response = await get_http_client().get(settings.FORECAST_URL, params={"lat": lat, "lon": lon})
        response.raise_for_status()
        return response.json()

    return await _cache.get_or_set((lat, lon), fetch)
