from typing import Optional

from fastapi import APIRouter, Query

from app.services.forecast_service import get_forecast_tramos
from app.services.ventusky_service import VentuskyService

router = APIRouter()

UNIDADES = {
    "td": "C",
    "sr": "mm",
    "rp": "%",
    "vd45": "°",
    "vsd": "km/h",
    "vg": "km/h",
}


@router.get("/ventusky")
async def get_pronostico(
    lat: float = Query(..., description="Latitud"),
    lon: float = Query(..., description="Longitud"),
    type: Optional[str] = Query(None, description="Tipo de pronóstico: 'h', 'd', 't'"),
):
    """
    Pronóstico diario y por tramos (servicio pronostico.iagro360).
    - lat/lon: coordenadas
    - type: se acepta por compatibilidad; siempre devuelve daily + tramos (hourly vacío).
    """
    forecast = await get_forecast_tramos(lat, lon)
    return {
        "ubicacion": {"lat": lat, "lon": lon},
        "unidades": UNIDADES,
        "hourly": [],
        "daily": forecast["daily"],
        "tramos": forecast["tramo"],
    }


@router.get("/v1/ventusky")
async def get_pronostico_v1(
    lat: float = Query(..., description="Latitud"),
    lon: float = Query(..., description="Longitud"),
    type: Optional[str] = Query(None, description="Tipo de pronóstico: 'hourly', 'daily', 'tramos'"),
):
    """
    Pronóstico de Ventusky (scraping):
    - lat/lon: coordenadas
    - type: 'h', 'd', 't'.
        - Si no se pasa, devuelve los 3 tipos juntos.
        - Si se pasa un valor inválido, devuelve {}
    """
    if type not in (None, "h", "d", "t"):
        return {}

    service = VentuskyService(lat, lon)
    await service.load_forecast()

    response = {
        "ubicacion": {
            "lat": service.note.get("lat", lat),
            "lon": service.note.get("lon", lon),
        },
        "unidades": UNIDADES,
    }
    if type in (None, "h"):
        response["hourly"] = service.get_forecast_hourly()
    if type in (None, "d"):
        response["daily"] = service.get_forecast_daily()
    if type in (None, "t"):
        response["tramos"] = service.get_forecast_by_tramos()
    return response
