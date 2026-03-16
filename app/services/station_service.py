
from django import db
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from app.models.Estacion import Estacion
from app.schemas.station import StationCreate
from fastapi import HTTPException

from app.services.api_service import ApiService



class StationService:

    @staticmethod
    async def asignation_station(
        db: AsyncSession,
        user_id: int,
        station: StationCreate
    ):

        result = await db.execute(
            select(Estacion).where(Estacion.codigo == station.codigo)
        )

        estacion = result.scalar_one_or_none()

        # estación no existe
        if not estacion:
            raise HTTPException(
            status_code=400,
            detail="La estación no existe"
        )

        # regla 1: no permitir estaciones públicas
        if estacion.is_public:
            raise HTTPException(
                status_code=400,
                detail="No puedes agregar una estación pública"
            )

        # regla 2: ya tiene dueño
        if estacion.user_id is not None:
            raise HTTPException(
                status_code=400,
                detail="La estación ya tiene un dueño"
            )

        # asignar estación al usuario
        estacion.user_id = user_id

        db.add(estacion)
        await db.commit()
        await db.refresh(estacion)

        return {
        "id": estacion.id,
        "codigo": estacion.codigo,
        "nombre": estacion.nombre,
        "modelo": estacion.modelo,
        "ubicacion": estacion.ubicacion,
        "latitud": estacion.latitud,
        "longitud": estacion.longitud,
        "descripcion": estacion.descripcion
    }
    
    @staticmethod
    async def estacion_get(
        db: AsyncSession,
        user_id: int,
    ):

        result = await db.execute(
            select(Estacion).where(Estacion.user_id == user_id)
        )

        estaciones = result.scalars().all()

        if not estaciones:
            return []

        estaciones_data = []
        apiService = ApiService(db)
        for estacion in estaciones:
            data_estacion = await apiService.get_latest_record(estacion.codigo)

            estaciones_data.append({
                "id": estacion.id,
                "codigo": estacion.codigo,
                "nombre": estacion.nombre,
                "modelo": estacion.modelo,
                "ubicacion": estacion.ubicacion,
                "latitud": estacion.latitud,
                "longitud": estacion.longitud,
                "descripcion": estacion.descripcion,
                "datos": data_estacion
            })
        return estaciones_data