from pydantic import BaseModel
from typing import Optional


class StationCreate(BaseModel):
    """Usado solo por el admin al crear una estación nueva."""
    codigo: str
    modelo: Optional[str] = None
    nombre: Optional[str] = None
    ubicacion: Optional[str] = None
    latitud: Optional[float] = None
    longitud: Optional[float] = None
    descripcion: Optional[str] = None
    is_public: bool = False
    max_usuarios: int = 1


class StationJoin(BaseModel):
    """Usado por el cliente para agregarse a una estación con código."""
    codigo: str


class StationResponse(BaseModel):
    id: int
    codigo: str
    nombre: Optional[str] = None
    modelo: Optional[str] = None
    ubicacion: Optional[str] = None
    latitud: Optional[float] = None
    longitud: Optional[float] = None
    descripcion: Optional[str] = None
    is_public: bool
    max_usuarios: Optional[int] = None
    datos: Optional[dict] = None

    class Config:
        from_attributes = True