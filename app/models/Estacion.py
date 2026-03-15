from sqlalchemy import String, Float, DateTime, ForeignKey, Boolean
from sqlalchemy.orm import Mapped, mapped_column, relationship
from datetime import datetime
from app.database import Base


class Estacion(Base):
    __tablename__ = "estacion"

    id: Mapped[int] = mapped_column(primary_key=True, index=True)

    codigo: Mapped[str] = mapped_column(String(50), unique=True, index=True, nullable=False)

    modelo: Mapped[str] = mapped_column(String(100), nullable=True)
    nombre: Mapped[str] = mapped_column(String(100), nullable=True)
    ubicacion: Mapped[str] = mapped_column(String(255), nullable=True)

    latitud: Mapped[float] = mapped_column(Float, nullable=True)
    longitud: Mapped[float] = mapped_column(Float, nullable=True)

    descripcion: Mapped[str] = mapped_column(String(255), nullable=True)

    is_public: Mapped[bool] = mapped_column(Boolean, default=False,nullable=True)

    # relación con usuario dueño
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id"), nullable=True)

    # relaciones
    datos: Mapped[list["SensorData"]] = relationship(
        "SensorData",
        back_populates="sensor",
        cascade="all, delete"
    )


class SensorData(Base):
    __tablename__ = "datos_sensores"

    id: Mapped[int] = mapped_column(primary_key=True, index=True)

    sensor_id: Mapped[str] = mapped_column(
        ForeignKey("estacion.codigo"),
        index=True
    )

    temperatura: Mapped[float] = mapped_column(Float, nullable=True)
    humedad: Mapped[float] = mapped_column(Float, nullable=True)
    lluvia: Mapped[float] = mapped_column(Float, nullable=True)

    velocidad_viento: Mapped[float] = mapped_column(Float, nullable=True)
    direccion_viento: Mapped[float] = mapped_column(Float, nullable=True)
    rafaga_viento: Mapped[float] = mapped_column(Float, nullable=True)

    presion_barometrica: Mapped[float] = mapped_column(Float, nullable=True)

    fecha: Mapped[datetime] = mapped_column(DateTime(timezone=True), index=True)

    # relación con estación
    sensor: Mapped["Estacion"] = relationship(
        "Estacion",
        back_populates="datos"
    )