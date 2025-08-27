from fastapi import APIRouter
from app.controllers.sensores import get_daily_summary_controller
from app.controllers.sensores import get_latest_record_controller
from app.schemas.response import ResponseDTO
from typing import List, Dict

router = APIRouter()

@router.get("/get/{sensor_id}", response_model=ResponseDTO[List[Dict]])
def all_sensor_data(sensor_id: str):
    return get_daily_summary_controller(sensor_id)

@router.get("/latest/{sensor_id}", response_model=ResponseDTO[Dict])
def latest_sensor_data(sensor_id: str):
    """
    Obtiene el último registro del sensor según sensor_id.
    """
    return get_latest_record_controller(sensor_id)