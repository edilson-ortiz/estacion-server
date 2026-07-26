from sqlalchemy import Integer, String, Float, DateTime, ForeignKey, Boolean, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column, relationship
from datetime import datetime
from app.database import Base
from app.models.user import User


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
    is_public: Mapped[bool] = mapped_column(Boolean, default=False, nullable=True)

    # 👇 NUEVO: cuántos usuarios (clientes) pueden vincularse a esta estación (licencias vendidas)
    max_usuarios: Mapped[int] = mapped_column(Integer, default=1, nullable=False)

    # Dueño/creador: SIEMPRE un admin o superadmin (se valida en el service, no aquí)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id"), nullable=True)
    propietario: Mapped["User"] = relationship(
        "User",
        back_populates="estaciones_creadas",
        foreign_keys=[user_id]
    )

    # Usuarios (clientes) vinculados a esta estación: quién la agregó, quién fue asignado
    usuarios: Mapped[list["EstacionUsuario"]] = relationship(
        "EstacionUsuario",
        back_populates="estacion",
        cascade="all, delete-orphan"
    )

    datos: Mapped[list["SensorData"]] = relationship(
        "SensorData",
        back_populates="sensor",
        cascade="all, delete"
    )
    calibraciones: Mapped[list["CalibracionPluviometro"]] = relationship(
        "CalibracionPluviometro",
        back_populates="estacion",
        order_by="CalibracionPluviometro.vigente_desde"
    )

class CalibracionPluviometro(Base):
    __tablename__ = "calibracion_pluviometro"

    id: Mapped[int] = mapped_column(primary_key=True, index=True)

    estacion_codigo: Mapped[str] = mapped_column(
        ForeignKey("estacion.codigo"),
        index=True,
        nullable=False
    )

    factor_k: Mapped[float] = mapped_column(Float, nullable=False, default=0.1)
    vigente_desde: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)

    motivo: Mapped[str] = mapped_column(String(255), nullable=True)
    creado_por: Mapped[str] = mapped_column(String(100), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=datetime.utcnow)

    # relación con estación
    estacion: Mapped["Estacion"] = relationship("Estacion", back_populates="calibraciones")

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

class EstacionUsuario(Base):
    """
    Tabla puente (many-to-many) entre User y Estacion.
    Representa el hecho de que un usuario "tiene agregada" una estación,
    ya sea porque la creó (rol=owner), se unió con el código (rol=viewer),
    o un admin lo agregó manualmente (rol=viewer).
    """
    __tablename__ = "estacion_usuario"
    __table_args__ = (
        UniqueConstraint("user_id", "estacion_id", name="uq_user_estacion"),
    )

    id: Mapped[int] = mapped_column(primary_key=True, index=True)

    user_id: Mapped[int] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), index=True)
    estacion_id: Mapped[int] = mapped_column(ForeignKey("estacion.id", ondelete="CASCADE"), index=True)

    rol: Mapped[str] = mapped_column(String(20), default="viewer")  # "owner" | "viewer"
    fecha_union: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=datetime.utcnow)

    # 👇 NUEVO: bloqueo administrativo (el usuario sigue vinculado, pero no puede ver la estación)
    is_blocked: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    blocked_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=True)
    blocked_reason: Mapped[str] = mapped_column(String(255), nullable=True)

    usuario: Mapped["User"] = relationship("User", back_populates="estaciones_vinculadas")
    estacion: Mapped["Estacion"] = relationship("Estacion", back_populates="usuarios")