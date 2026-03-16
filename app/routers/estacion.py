from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession
from app.database import get_db
from app.models.user import User
from app.schemas.response import ResponseDTO
from app.schemas.response import ResponseDTO
from app.schemas.station import StationCreate, StationResponse
from app.schemas.user import  UserResponse
from app.services.auth_service import AuthService
from app.dependencies.auth import get_current_user
from app.services.station_service import StationService

router = APIRouter(prefix="/api", tags=["Estación"])

@router.post("/stations", response_model=ResponseDTO[StationResponse])
async def create_station(station_data: StationCreate,db: AsyncSession = Depends(get_db),current_user: User = Depends(get_current_user)):

    station = await StationService.asignation_station(
        db,
        current_user.id,
        station_data
    )
    return ResponseDTO(
        success=True,
        message="Estación agregada correctamente",
        data=station
    )
  

@router.get("/stations", response_model=ResponseDTO[list[StationResponse]])
async def get(db: AsyncSession = Depends(get_db),current_user: User = Depends(get_current_user)):
    # Devuelve el objeto completo
    station = await StationService.estacion_get(
        db,
        current_user.id
    )
    return ResponseDTO(
        success=True,
        message="Stations retrieved",
        data=station
    )

