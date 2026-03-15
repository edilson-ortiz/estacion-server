from fastapi import APIRouter,Query
from app.services.pronostico_service import PronosticoService
from app.services.ventuski_service import VentuskyService
from typing import Optional

router = APIRouter()


@router.get("/pronostico_met")
async def get_pronostico(lat: float, lon: float):
    service = PronosticoService()
    data = await service.get_met_no(lat,lon)
    return data

@router.get("/ventusky")
async def get_pronostico(
    lat: float = Query(..., description="Latitud"),
    lon: float = Query(..., description="Longitud"),
    type: Optional[str] = Query(None, description="Tipo de pronóstico: 'hourly', 'daily', 'tramos'")
):
    """
    Devuelve pronóstico de Ventusky según parámetros:
    - lat/lon: coordenadas
    - type: 'h', 'd', 't'. 
        - Si no se pasa, devuelve los 3 tipos juntos.
        - Si se pasa un valor inválido, devuelve {}
    """

    service = VentuskyService(lat, lon)
    await service.load_forecast()  # Llama a Ventusky una sola vez

    response = {
        "ubicacion": {
            "lat": service.note.get("lat", lat),
            "lon": service.note.get("lon", lon)
        },
        "unidades": {
            "td": "C",
            "sr": "mm",
            "rp": "%",
            "vd45": "°",
            "vsd": "km/h",
            "vg": "km/h"
        }
    }

    if type == "h":
        response["hourly"] = service.get_forecast_hourly()
    elif type == "d":
        response["daily"] = service.get_forecast_daily()
    elif type == "t":
        response["tramos"] = service.get_forecast_by_tramos()
    elif type is None:
        # Devuelve los 3 tipos
        response["hourly"] = service.get_forecast_hourly()
        response["daily"] = service.get_forecast_daily()
        response["tramos"] = service.get_forecast_by_tramos()
    else:
        return {}  # Tipo inválido

    return response