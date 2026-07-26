from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.models.user import User
from app.schemas.response import ResponseDTO
from app.schemas.station import StationCreate, StationJoin, StationResponse
from app.dependencies.auth import get_current_user
from app.services.station_service import StationService

router = APIRouter(prefix="/api", tags=["Estación"])


@router.post("/stations", response_model=ResponseDTO[StationResponse])
async def create_station(
    station_data: StationCreate,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    station = await StationService.create_station(db, current_user, station_data)
    return ResponseDTO(success=True, message="Estación creada correctamente", data=station)


@router.get("/stations")
async def get_stations(
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    data = await StationService.get_stations_view(db, current_user)
    return ResponseDTO(success=True, message="Estaciones obtenidas", data=data)


@router.post("/stations/join")
async def join_station(
    payload: StationJoin,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    vinculo = await StationService.join_by_code(db, current_user, payload.codigo)
    return ResponseDTO(success=True, message="Estación agregada a tu cuenta", data={"estacion_id": vinculo.estacion_id})


@router.delete("/stations/{codigo}/leave")
async def leave_station(
    codigo: str,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    await StationService.leave_station(db, current_user, codigo)
    return ResponseDTO(success=True, message="Estación quitada de tu cuenta", data=None)


@router.post("/stations/{codigo}/users/{user_id}")
async def admin_add_user(
    codigo: str,
    user_id: int,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    vinculo = await StationService.admin_add_user(db, current_user, codigo, user_id)
    return ResponseDTO(success=True, message="Usuario agregado a la estación", data={"user_id": vinculo.user_id})


@router.delete("/stations/{codigo}/users/{user_id}")
async def admin_remove_user(
    codigo: str,
    user_id: int,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    await StationService.admin_remove_user(db, current_user, codigo, user_id)
    return ResponseDTO(success=True, message="Usuario quitado de la estación", data=None)


@router.patch("/stations/{codigo}/users/{user_id}/block")
async def admin_block_user(
    codigo: str,
    user_id: int,
    blocked: bool,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    vinculo = await StationService.admin_block_user(db, current_user, codigo, user_id, blocked)
    estado = "bloqueado" if blocked else "desbloqueado"
    return ResponseDTO(success=True, message=f"Usuario {estado} correctamente", data=None)

@router.get("/stations/{codigo}/rain-12h")
async def get_rain_last_12h(
    codigo: str,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    data = await StationService.get_rain_last_12h(db, current_user, codigo)
    return ResponseDTO(success=True, message="Lluvia últimas 12h obtenida", data=data)