from sqlalchemy import String, Boolean, Enum
from sqlalchemy.orm import Mapped, mapped_column, relationship
from app.database import Base
import enum



class UserRole(str, enum.Enum):
    client = "client"
    admin = "admin"
    superadmin = "superadmin"


class User(Base):
    __tablename__ = "users"

    id: Mapped[int] = mapped_column(primary_key=True, index=True)
    email: Mapped[str] = mapped_column(String(255), unique=True, index=True)
    hashed_password: Mapped[str] = mapped_column(String(255))
    first_name: Mapped[str] = mapped_column(String(50))
    last_name: Mapped[str] = mapped_column(String(50))
    phone: Mapped[str] = mapped_column(String(20), nullable=True)
    role: Mapped[UserRole] = mapped_column(Enum(UserRole), default=UserRole.client)
    activity: Mapped[str] = mapped_column(String(100), nullable=True)
    terms_accepted: Mapped[bool] = mapped_column(Boolean, default=False)
    public_station_access: Mapped[bool] = mapped_column(Boolean, default=True)
    session_id: Mapped[str] = mapped_column(String(255), nullable=True)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)  # ✅ coma eliminada

    # Estaciones donde este usuario (admin) figura como dueño/creador
    estaciones_creadas: Mapped[list["Estacion"]] = relationship(
        "Estacion",
        back_populates="propietario",
        foreign_keys="Estacion.user_id"
    )

    # Vínculos de este usuario con estaciones (agregadas por código, o asignadas por admin)
    estaciones_vinculadas: Mapped[list["EstacionUsuario"]] = relationship(
        "EstacionUsuario",
        back_populates="usuario",
        cascade="all, delete-orphan"
    )