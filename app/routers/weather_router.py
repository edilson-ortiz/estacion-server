from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from app.database import get_db
from app.services.weather_service import WeatherService
from app.services.pronostico_service import PronosticoService
from app.schemas.sensor_data import SensorDataResponse
from app.schemas.response import ResponseDTO  # tu DTO ya existente
from typing import List, Dict
from datetime import datetime

router = APIRouter()

@router.get("/get/{sensor_id}", response_model=ResponseDTO[List[Dict]])
async def all_sensor_data(sensor_id: str, db: Session = Depends(get_db)):
    service = WeatherService(db)
    resumen = await service.get_daily_summary(sensor_id)
    if resumen:
        return ResponseDTO(success=True, message=f"Datos de los últimos 30 días para {sensor_id}", data=resumen)
    return ResponseDTO(success=False, message=f"No hay datos de los últimos 30 días para {sensor_id}", data=[])

@router.get("/latest/{sensor_id}", response_model=ResponseDTO[Dict])
async def latest_sensor_data(sensor_id: str, db: Session = Depends(get_db)):
    service = WeatherService(db)
    registro = await service.get_latest_record(sensor_id)
    if registro:
        return ResponseDTO(
            success=True, 
            message=f"Último registro de {sensor_id}", 
            data=registro
        )
    return ResponseDTO(
        success=False, 
        message=f"No hay registros para {sensor_id}", 
        data={}
    )

@router.get("/monthly_rain/{sensor_id}/{year}/{month}", response_model=ResponseDTO[List[Dict]])
async def monthly_rain(sensor_id: str, year: int, month: int, db: Session = Depends(get_db)):
    service = WeatherService(db)
    registro = await service.get_monthly_daily_rain(sensor_id, year, month)
    if registro:
        return ResponseDTO(
            success=True,
            message=f"Registro mes {month} sensor {sensor_id}",
            data=registro
        )
    return ResponseDTO(
        success=False,
        message=f"No hay registros para {sensor_id} en {year}-{month}",
        data=[]
    )

@router.get("/year_rain/{sensor_id}/{year}", response_model=ResponseDTO[List[Dict]])
async def year_rain(sensor_id: str, year: int, db: Session = Depends(get_db)):
    service = WeatherService(db)
    registro = await service.get_year_daily_rain(sensor_id, year)
    if registro:
        return ResponseDTO(
            success=True,
            message=f"Registro anio {year} sensor {sensor_id}",
            data=registro
        )
    return ResponseDTO(
        success=False,
        message=f"No hay registros para {sensor_id} en {year}",
        data=[]
    )

@router.get("/rain_sum/{sensor_id}/{start_date}/{end_date}", response_model=ResponseDTO[float])
async def rain_sum(sensor_id: str, start_date: str, end_date: str, db: Session = Depends(get_db)):

    """
    Devuelve la lluvia total acumulada entre dos fechas (inclusive).
    Ejemplo: /rain_sum/TR10/2025-10-01/2025-10-05
    """
    try:
        # Convertir las fechas del path a objetos datetime
        fecha_inicio = datetime.strptime(start_date, "%Y-%m-%d")
        fecha_fin = datetime.strptime(end_date, "%Y-%m-%d")

        service = WeatherService(db)
        suma_lluvia = await service.get_rain_sum_between_dates(sensor_id, fecha_inicio, fecha_fin)

        return ResponseDTO(
            success=True,
            message=f"Lluvia acumulada desde {start_date} hasta {end_date} para el sensor {sensor_id}",
            data=suma_lluvia
        )

    except ValueError:
        return ResponseDTO(
            success=False,
            message="Formato de fecha inválido. Usa el formato YYYY-MM-DD.",
            data=0.0
        )