from fastapi import APIRouter
from app.services.pronostico_service import PronosticoService

router = APIRouter()


@router.get("/pronostico_met")
async def get_pronostico(lat: float, lon: float):
    service = PronosticoService()
    data = await service.get_met_no(lat,lon)
    return data
