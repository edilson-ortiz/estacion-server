from pydantic import BaseModel
from datetime import datetime

class SensorDataBase(BaseModel):
    sensor_id: str
    temperatura: float
    humedad: float
    lluvia: float
    fecha: datetime
    velocidad_viento: float
    direccion_viento: float
    rafaga_viento: float
    presion_barometrica: float

class SensorDataResponse(SensorDataBase):
    id: int

    class Config:
        from_attributes = True
