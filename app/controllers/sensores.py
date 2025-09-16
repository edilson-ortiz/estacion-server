from app.models.datos_sensores import get_daily_summary
from app.models.datos_sensores import get_latest_record
from app.schemas.response import ResponseDTO
from typing import List, Dict

def get_daily_summary_controller(sensor_id: str) -> ResponseDTO[List[Dict]]:
    resumen = get_daily_summary(sensor_id)
    if resumen and isinstance(resumen, list):
        return ResponseDTO(
            success=True,
            message=f"Datos de los últimos 30 días para el sensor {sensor_id}",
            data=resumen
        )
    return ResponseDTO(
        success=False,
        message=f"No hay datos de los últimos 30 días para el sensor {sensor_id}",
        data=[]
    )

def get_latest_record_controller(sensor_id: str) -> ResponseDTO[Dict]:
    registro = get_latest_record(sensor_id)
    
    # Comprobamos si devolvió un registro válido
    if registro and "message" not in registro:
        return ResponseDTO(
            success=True,
            message=f"Último registro del sensor {sensor_id}",
            data=registro
        )
    
    return ResponseDTO(
        success=False,
        message=f"No hay registros para el sensor {sensor_id}",
        data={}
    )