from __future__ import annotations

from datetime import datetime
from typing import TYPE_CHECKING

from sqlalchemy import DateTime, Float, ForeignKey, Index
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base

if TYPE_CHECKING:
    from app.models.estacion import Estacion


class SensorData(Base):
    """Lectura de una estación. La lluvia se guarda en pulsos crudos (ver CalibracionPluviometro)."""
    __tablename__ = "datos_sensores"
    __table_args__ = (
        # Casi todas las consultas filtran por estación + rango de fechas
        Index("ix_datos_sensores_sensor_id_fecha", "sensor_id", "fecha"),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    sensor_id: Mapped[str] = mapped_column(ForeignKey("estacion.codigo"))

    temperatura: Mapped[float | None] = mapped_column(Float, nullable=True)
    humedad: Mapped[float | None] = mapped_column(Float, nullable=True)
    lluvia: Mapped[float | None] = mapped_column(Float, nullable=True)

    velocidad_viento: Mapped[float | None] = mapped_column(Float, nullable=True)
    direccion_viento: Mapped[float | None] = mapped_column(Float, nullable=True)
    rafaga_viento: Mapped[float | None] = mapped_column(Float, nullable=True)

    presion_barometrica: Mapped[float | None] = mapped_column(Float, nullable=True)

    fecha: Mapped[datetime] = mapped_column(DateTime(timezone=True), index=True)

    sensor: Mapped[Estacion] = relationship("Estacion", back_populates="datos")
