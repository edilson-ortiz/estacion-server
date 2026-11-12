"""Importa todos los modelos para que SQLAlchemy resuelva las relaciones y Alembic los vea."""
from app.models.estacion import CalibracionPluviometro, Estacion, EstacionRol, EstacionUsuario
from app.models.sensor_data import SensorData
from app.models.user import ADMIN_ROLES, User, UserRole

__all__ = [
    "ADMIN_ROLES",
    "CalibracionPluviometro",
    "Estacion",
    "EstacionRol",
    "EstacionUsuario",
    "SensorData",
    "User",
    "UserRole",
]
