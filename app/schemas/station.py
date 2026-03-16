from alembic.environment import Any, Dict
from pydantic import BaseModel
from typing import Generic, TypeVar, List, Optional

from app.routers import estacion

class StationCreate(BaseModel):
    codigo: str

class StationResponse(BaseModel):
    id: int
    codigo: str = None
    nombre: str = None
    modelo: str = None
    ubicacion: str = None
    latitud: float = None
    longitud: float = None
    descripcion: Optional[str] = None

    datos: Optional[Dict[str, Any]] = None
    

    class Config:
        from_attributes = True
