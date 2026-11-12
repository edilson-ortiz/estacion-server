from __future__ import annotations

from datetime import datetime
from typing import TYPE_CHECKING

from sqlalchemy import Boolean, DateTime, Float, ForeignKey, Integer, String, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.time import utcnow
from app.db.base import Base

if TYPE_CHECKING:
    from app.models.sensor_data import SensorData
    from app.models.user import User


class EstacionRol:
    """Valores de EstacionUsuario.rol."""
    OWNER = "owner"
    VIEWER = "viewer"


class Estacion(Base):
    __tablename__ = "estacion"

    id: Mapped[int] = mapped_column(primary_key=True, index=True)
    codigo: Mapped[str] = mapped_column(String(50), unique=True, index=True, nullable=False)

    modelo: Mapped[str | None] = mapped_column(String(100), nullable=True)
    nombre: Mapped[str | None] = mapped_column(String(100), nullable=True)
    ubicacion: Mapped[str | None] = mapped_column(String(255), nullable=True)

    latitud: Mapped[float | None] = mapped_column(Float, nullable=True)
    longitud: Mapped[float | None] = mapped_column(Float, nullable=True)

    descripcion: Mapped[str | None] = mapped_column(String(255), nullable=True)
    is_public: Mapped[bool | None] = mapped_column(Boolean, default=False, nullable=True)

    # Cuántos usuarios (clientes) pueden vincularse a esta estación (licencias vendidas)
    max_usuarios: Mapped[int] = mapped_column(Integer, default=1, nullable=False)

    # Dueño/creador: siempre un admin o superadmin (se valida en el service)
    user_id: Mapped[int | None] = mapped_column(ForeignKey("users.id"), nullable=True)
    propietario: Mapped[User | None] = relationship(
        "User", back_populates="estaciones_creadas", foreign_keys=[user_id]
    )

    # Usuarios vinculados a esta estación (dueño, unidos por código o asignados por admin)
    usuarios: Mapped[list[EstacionUsuario]] = relationship(
        "EstacionUsuario", back_populates="estacion", cascade="all, delete-orphan"
    )

    datos: Mapped[list[SensorData]] = relationship(
        "SensorData", back_populates="sensor", cascade="all, delete"
    )

    calibraciones: Mapped[list[CalibracionPluviometro]] = relationship(
        "CalibracionPluviometro",
        back_populates="estacion",
        order_by="CalibracionPluviometro.vigente_desde",
    )


class CalibracionPluviometro(Base):
    """Factor de conversión pulsos → mm del pluviómetro, con vigencia desde una fecha."""
    __tablename__ = "calibracion_pluviometro"

    id: Mapped[int] = mapped_column(primary_key=True, index=True)
    estacion_codigo: Mapped[str] = mapped_column(
        ForeignKey("estacion.codigo"), index=True, nullable=False
    )

    factor_k: Mapped[float] = mapped_column(Float, nullable=False, default=0.1)
    vigente_desde: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)

    motivo: Mapped[str | None] = mapped_column(String(255), nullable=True)
    creado_por: Mapped[str | None] = mapped_column(String(100), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)

    estacion: Mapped[Estacion] = relationship("Estacion", back_populates="calibraciones")


class EstacionUsuario(Base):
    """Tabla puente (many-to-many) entre User y Estacion.

    Un usuario "tiene agregada" una estación porque la creó (rol=owner),
    se unió con el código (rol=viewer) o un admin lo agregó (rol=viewer).
    """
    __tablename__ = "estacion_usuario"
    __table_args__ = (UniqueConstraint("user_id", "estacion_id", name="uq_user_estacion"),)

    id: Mapped[int] = mapped_column(primary_key=True, index=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), index=True)
    estacion_id: Mapped[int] = mapped_column(
        ForeignKey("estacion.id", ondelete="CASCADE"), index=True
    )

    rol: Mapped[str] = mapped_column(String(20), default=EstacionRol.VIEWER)
    fecha_union: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)

    # Bloqueo administrativo: sigue vinculado, pero no puede ver la estación
    is_blocked: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    blocked_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    blocked_reason: Mapped[str | None] = mapped_column(String(255), nullable=True)

    usuario: Mapped[User] = relationship("User", back_populates="estaciones_vinculadas")
    estacion: Mapped[Estacion] = relationship("Estacion", back_populates="usuarios")
