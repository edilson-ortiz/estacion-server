from fastapi import HTTPException
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.time import utcnow
from app.models import Estacion, EstacionRol, EstacionUsuario, User
from app.schemas.station import StationCreate
from app.services.weather_service import WeatherService


def _ensure_admin(user: User, detail: str) -> None:
    if not user.is_admin:
        raise HTTPException(status_code=403, detail=detail)


def _estacion_dict(e: Estacion, datos: dict | None, **extra) -> dict:
    return {
        "id": e.id,
        "codigo": e.codigo,
        "nombre": e.nombre,
        "modelo": e.modelo,
        "ubicacion": e.ubicacion,
        "latitud": e.latitud,
        "longitud": e.longitud,
        "descripcion": e.descripcion,
        "is_public": e.is_public,
        **extra,
        "datos": datos,
    }


class StationService:

    # ------------------------------------------------------------------
    # Helpers internos
    # ------------------------------------------------------------------
    @staticmethod
    async def _get_estacion_by_codigo(db: AsyncSession, codigo: str) -> Estacion:
        result = await db.execute(select(Estacion).where(Estacion.codigo == codigo))
        estacion = result.scalar_one_or_none()
        if not estacion:
            raise HTTPException(status_code=404, detail="Código de estación inválido.")
        return estacion

    @staticmethod
    async def _get_vinculo(db: AsyncSession, user_id: int, estacion_id: int) -> EstacionUsuario | None:
        result = await db.execute(
            select(EstacionUsuario).where(
                EstacionUsuario.user_id == user_id,
                EstacionUsuario.estacion_id == estacion_id,
            )
        )
        return result.scalar_one_or_none()

    @staticmethod
    async def _count_viewers(db: AsyncSession, estacion_id: int) -> int:
        result = await db.execute(
            select(func.count()).select_from(EstacionUsuario).where(
                EstacionUsuario.estacion_id == estacion_id,
                EstacionUsuario.rol == EstacionRol.VIEWER,
            )
        )
        return result.scalar_one()

    @staticmethod
    async def _get_vinculo_gestionable(
        db: AsyncSession, codigo: str, target_user_id: int, owner_detail: str
    ) -> EstacionUsuario:
        """Vínculo de otro usuario que un admin puede modificar (no el del dueño)."""
        estacion = await StationService._get_estacion_by_codigo(db, codigo)
        vinculo = await StationService._get_vinculo(db, target_user_id, estacion.id)
        if not vinculo:
            raise HTTPException(status_code=404, detail="El usuario no está vinculado a esta estación.")
        if vinculo.rol == EstacionRol.OWNER:
            raise HTTPException(status_code=400, detail=owner_detail)
        return vinculo

    @staticmethod
    async def _add_viewer(db: AsyncSession, user_id: int, estacion_id: int) -> EstacionUsuario:
        vinculo = EstacionUsuario(user_id=user_id, estacion_id=estacion_id, rol=EstacionRol.VIEWER)
        db.add(vinculo)
        await db.commit()
        await db.refresh(vinculo)
        return vinculo

    # ------------------------------------------------------------------
    # ADMIN: crear estación
    # ------------------------------------------------------------------
    @staticmethod
    async def create_station(db: AsyncSession, admin: User, data: StationCreate) -> Estacion:
        _ensure_admin(admin, "Solo un admin puede crear estaciones.")

        result = await db.execute(select(Estacion.id).where(Estacion.codigo == data.codigo))
        if result.scalar_one_or_none() is not None:
            raise HTTPException(status_code=400, detail="Ese código de estación ya existe.")

        estacion = Estacion(**data.model_dump(), user_id=admin.id)
        db.add(estacion)
        await db.flush()
        db.add(EstacionUsuario(user_id=admin.id, estacion_id=estacion.id, rol=EstacionRol.OWNER))
        await db.commit()
        await db.refresh(estacion)
        return estacion

    # ------------------------------------------------------------------
    # Listado combinado: públicas + mis estaciones vinculadas
    # ------------------------------------------------------------------
    @staticmethod
    async def get_stations_view(db: AsyncSession, user: User) -> dict:
        publicas = (await db.execute(select(Estacion).where(Estacion.is_public == True))).scalars().all()  # noqa: E712

        mias = (
            await db.execute(
                select(EstacionUsuario.rol, Estacion)
                .join(Estacion, Estacion.id == EstacionUsuario.estacion_id)
                .where(
                    EstacionUsuario.user_id == user.id,
                    EstacionUsuario.is_blocked == False,  # noqa: E712
                )
            )
        ).all()

        # Datos en vivo de TODAS las estaciones en 2 consultas (antes: 2 por estación)
        codigos = [e.codigo for e in publicas] + [e.codigo for _, e in mias]
        datos = await WeatherService(db).get_latest_datos_many(codigos)

        return {
            "publicas": [_estacion_dict(e, datos.get(e.codigo)) for e in publicas],
            "mis_estaciones": [_estacion_dict(e, datos.get(e.codigo), rol=rol) for rol, e in mias],
        }

    # ------------------------------------------------------------------
    # CLIENTE: agregarse a una estación por código (solo privadas)
    # ------------------------------------------------------------------
    @staticmethod
    async def join_by_code(db: AsyncSession, user: User, codigo: str) -> EstacionUsuario:
        estacion = await StationService._get_estacion_by_codigo(db, codigo)

        if estacion.is_public:
            raise HTTPException(status_code=400, detail="Esta estación es pública, no necesitas agregarla.")

        if await StationService._get_vinculo(db, user.id, estacion.id):
            raise HTTPException(status_code=400, detail="Ya tienes esta estación agregada.")

        if await StationService._count_viewers(db, estacion.id) >= estacion.max_usuarios:
            raise HTTPException(
                status_code=400,
                detail=f"Esta estación alcanzó su límite de {estacion.max_usuarios} usuario(s).",
            )

        return await StationService._add_viewer(db, user.id, estacion.id)

    # ------------------------------------------------------------------
    # CLIENTE: quitarse una estación
    # ------------------------------------------------------------------
    @staticmethod
    async def leave_station(db: AsyncSession, user: User, codigo: str) -> None:
        estacion = await StationService._get_estacion_by_codigo(db, codigo)
        vinculo = await StationService._get_vinculo(db, user.id, estacion.id)

        if not vinculo:
            raise HTTPException(status_code=404, detail="No tienes esta estación agregada.")
        if vinculo.rol == EstacionRol.OWNER:
            raise HTTPException(status_code=400, detail="El dueño no puede quitarse su propia estación.")

        await db.delete(vinculo)
        await db.commit()

    # ------------------------------------------------------------------
    # ADMIN: agregar usuario manualmente
    # ------------------------------------------------------------------
    @staticmethod
    async def admin_add_user(db: AsyncSession, admin: User, codigo: str, target_user_id: int) -> EstacionUsuario:
        _ensure_admin(admin, "Solo un admin puede gestionar usuarios.")
        estacion = await StationService._get_estacion_by_codigo(db, codigo)

        if await StationService._get_vinculo(db, target_user_id, estacion.id):
            raise HTTPException(status_code=400, detail="El usuario ya está vinculado a esta estación.")

        if await StationService._count_viewers(db, estacion.id) >= estacion.max_usuarios:
            raise HTTPException(status_code=400, detail="Se alcanzó el límite de licencias de esta estación.")

        return await StationService._add_viewer(db, target_user_id, estacion.id)

    # ------------------------------------------------------------------
    # ADMIN: quitar usuario de una estación
    # ------------------------------------------------------------------
    @staticmethod
    async def admin_remove_user(db: AsyncSession, admin: User, codigo: str, target_user_id: int) -> None:
        _ensure_admin(admin, "Solo un admin puede gestionar usuarios.")
        vinculo = await StationService._get_vinculo_gestionable(
            db, codigo, target_user_id, "No se puede quitar al dueño de la estación."
        )
        await db.delete(vinculo)
        await db.commit()

    # ------------------------------------------------------------------
    # ADMIN: bloquear / desbloquear usuario
    # ------------------------------------------------------------------
    @staticmethod
    async def admin_block_user(
        db: AsyncSession, admin: User, codigo: str, target_user_id: int, blocked: bool
    ) -> EstacionUsuario:
        _ensure_admin(admin, "Solo un admin puede bloquear usuarios.")
        vinculo = await StationService._get_vinculo_gestionable(
            db, codigo, target_user_id, "No se puede bloquear al dueño."
        )
        vinculo.is_blocked = blocked
        vinculo.blocked_at = utcnow() if blocked else None
        await db.commit()
        await db.refresh(vinculo)
        return vinculo

    # ------------------------------------------------------------------
    # Lluvia de las últimas 12h (valida acceso a estaciones privadas)
    # ------------------------------------------------------------------
    @staticmethod
    async def get_rain_last_12h(db: AsyncSession, user: User, codigo: str) -> dict:
        estacion = await StationService._get_estacion_by_codigo(db, codigo)

        if not estacion.is_public:
            vinculo = await StationService._get_vinculo(db, user.id, estacion.id)
            if not vinculo or vinculo.is_blocked:
                raise HTTPException(status_code=403, detail="No tienes acceso a esta estación.")

        return await WeatherService(db).get_last_12h_rain(codigo)
