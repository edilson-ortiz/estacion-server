import asyncio
from sqlalchemy import select, func
from sqlalchemy.ext.asyncio import AsyncSession
from fastapi import HTTPException
from datetime import datetime

from app.models.Estacion import Estacion, EstacionUsuario
from app.models.user import User, UserRole
from app.schemas.station import StationCreate
from app.services.weather_service import WeatherService


class StationService:

    # ------------------------------------------------------------------
    # Helper interno: busca estación por código o lanza 404
    # ------------------------------------------------------------------
    @staticmethod
    async def _get_estacion_by_codigo(db: AsyncSession, codigo: str) -> Estacion:
        result = await db.execute(select(Estacion).where(Estacion.codigo == codigo))
        estacion = result.scalar_one_or_none()
        if not estacion:
            raise HTTPException(status_code=404, detail="Código de estación inválido.")
        return estacion

    # ------------------------------------------------------------------
    # ADMIN: crear estación
    # ------------------------------------------------------------------
    @staticmethod
    async def create_station(db: AsyncSession, admin: User, data: StationCreate):
        if admin.role not in (UserRole.admin, UserRole.superadmin):
            raise HTTPException(status_code=403, detail="Solo un admin puede crear estaciones.")

        result = await db.execute(select(Estacion).where(Estacion.codigo == data.codigo))
        if result.scalar_one_or_none():
            raise HTTPException(status_code=400, detail="Ese código de estación ya existe.")

        estacion = Estacion(
            codigo=data.codigo,
            modelo=data.modelo,
            nombre=data.nombre,
            ubicacion=data.ubicacion,
            latitud=data.latitud,
            longitud=data.longitud,
            descripcion=data.descripcion,
            is_public=data.is_public,
            max_usuarios=data.max_usuarios,
            user_id=admin.id,
        )
        db.add(estacion)
        await db.flush()

        vinculo = EstacionUsuario(user_id=admin.id, estacion_id=estacion.id, rol="owner")
        db.add(vinculo)

        await db.commit()
        await db.refresh(estacion)
        return estacion

    # ------------------------------------------------------------------
    # Listado combinado: públicas + mis estaciones vinculadas
    # ------------------------------------------------------------------
    @staticmethod
    async def get_stations_view(db: AsyncSession, user: User):
        apiService = WeatherService(db)

        # ---------------- Públicas ----------------
        result_pub = await db.execute(select(Estacion).where(Estacion.is_public == True))
        publicas = result_pub.scalars().all()

        # Trae los datos en vivo de todas las públicas en PARALELO, no una por una
        datos_publicas = await asyncio.gather(
            *[apiService.get_latest_record_pro(e.codigo) for e in publicas]
        )

        publicas_data = [
            {
                "id": e.id,
                "codigo": e.codigo,
                "nombre": e.nombre,
                "modelo": e.modelo,
                "ubicacion": e.ubicacion,
                "latitud": e.latitud,
                "longitud": e.longitud,
                "descripcion": e.descripcion,
                "is_public": e.is_public,
                "datos": datos.get("datos") if datos else None,
            }
            for e, datos in zip(publicas, datos_publicas)
        ]

        # ---------------- Mis estaciones (JOIN en una sola query) ----------------
        result = await db.execute(
            select(EstacionUsuario, Estacion)
            .join(Estacion, Estacion.id == EstacionUsuario.estacion_id)
            .where(
                EstacionUsuario.user_id == user.id,
                EstacionUsuario.is_blocked == False
            )
        )
        filas = result.all()  # lista de tuplas (EstacionUsuario, Estacion)

        datos_mias = await asyncio.gather(
            *[apiService.get_latest_record_pro(estacion.codigo) for _, estacion in filas]
        )

        mis_estaciones = [
            {
                "id": estacion.id,
                "codigo": estacion.codigo,
                "nombre": estacion.nombre,
                "modelo": estacion.modelo,
                "ubicacion": estacion.ubicacion,
                "latitud": estacion.latitud,
                "longitud": estacion.longitud,
                "descripcion": estacion.descripcion,
                "is_public": estacion.is_public,
                "rol": vinculo.rol,
                "datos": datos.get("datos") if datos else None,
            }
            for (vinculo, estacion), datos in zip(filas, datos_mias)
        ]

        return {
            "publicas": publicas_data,
            "mis_estaciones": mis_estaciones,
        }

    # ------------------------------------------------------------------
    # CLIENTE: agregarse a una estación por código (SOLO privadas)
    # ------------------------------------------------------------------
    @staticmethod
    async def join_by_code(db: AsyncSession, user: User, codigo: str):
        estacion = await StationService._get_estacion_by_codigo(db, codigo)

        # 👇 nueva regla: no tiene sentido "unirse" a una pública, ya la ve
        if estacion.is_public:
            raise HTTPException(
                status_code=400,
                detail="Esta estación es pública, no necesitas agregarla."
            )

        result_v = await db.execute(
            select(EstacionUsuario).where(
                EstacionUsuario.user_id == user.id,
                EstacionUsuario.estacion_id == estacion.id
            )
        )
        if result_v.scalar_one_or_none():
            raise HTTPException(status_code=400, detail="Ya tienes esta estación agregada.")

        result_count = await db.execute(
            select(func.count()).select_from(EstacionUsuario).where(
                EstacionUsuario.estacion_id == estacion.id,
                EstacionUsuario.rol == "viewer"
            )
        )
        cantidad_actual = result_count.scalar()

        if cantidad_actual >= estacion.max_usuarios:
            raise HTTPException(
                status_code=400,
                detail=f"Esta estación alcanzó su límite de {estacion.max_usuarios} usuario(s)."
            )

        vinculo = EstacionUsuario(user_id=user.id, estacion_id=estacion.id, rol="viewer")
        db.add(vinculo)
        await db.commit()
        await db.refresh(vinculo)
        return vinculo

    # ------------------------------------------------------------------
    # CLIENTE: quitarse una estación (por código)
    # ------------------------------------------------------------------
    @staticmethod
    async def leave_station(db: AsyncSession, user: User, codigo: str):
        estacion = await StationService._get_estacion_by_codigo(db, codigo)

        result = await db.execute(
            select(EstacionUsuario).where(
                EstacionUsuario.user_id == user.id,
                EstacionUsuario.estacion_id == estacion.id
            )
        )
        vinculo = result.scalar_one_or_none()

        if not vinculo:
            raise HTTPException(status_code=404, detail="No tienes esta estación agregada.")

        if vinculo.rol == "owner":
            raise HTTPException(status_code=400, detail="El dueño no puede quitarse su propia estación.")

        await db.delete(vinculo)
        await db.commit()

    # ------------------------------------------------------------------
    # ADMIN: agregar usuario manualmente (por código de estación)
    # ------------------------------------------------------------------
    @staticmethod
    async def admin_add_user(db: AsyncSession, admin: User, codigo: str, target_user_id: int):
        if admin.role not in (UserRole.admin, UserRole.superadmin):
            raise HTTPException(status_code=403, detail="Solo un admin puede gestionar usuarios.")

        estacion = await StationService._get_estacion_by_codigo(db, codigo)

        result_v = await db.execute(
            select(EstacionUsuario).where(
                EstacionUsuario.user_id == target_user_id,
                EstacionUsuario.estacion_id == estacion.id
            )
        )
        if result_v.scalar_one_or_none():
            raise HTTPException(status_code=400, detail="El usuario ya está vinculado a esta estación.")

        result_count = await db.execute(
            select(func.count()).select_from(EstacionUsuario).where(
                EstacionUsuario.estacion_id == estacion.id,
                EstacionUsuario.rol == "viewer"
            )
        )
        if result_count.scalar() >= estacion.max_usuarios:
            raise HTTPException(status_code=400, detail="Se alcanzó el límite de licencias de esta estación.")

        vinculo = EstacionUsuario(user_id=target_user_id, estacion_id=estacion.id, rol="viewer")
        db.add(vinculo)
        await db.commit()
        await db.refresh(vinculo)
        return vinculo

    # ------------------------------------------------------------------
    # ADMIN: quitar usuario de una estación (por código)
    # ------------------------------------------------------------------
    @staticmethod
    async def admin_remove_user(db: AsyncSession, admin: User, codigo: str, target_user_id: int):
        if admin.role not in (UserRole.admin, UserRole.superadmin):
            raise HTTPException(status_code=403, detail="Solo un admin puede gestionar usuarios.")

        estacion = await StationService._get_estacion_by_codigo(db, codigo)

        result = await db.execute(
            select(EstacionUsuario).where(
                EstacionUsuario.user_id == target_user_id,
                EstacionUsuario.estacion_id == estacion.id
            )
        )
        vinculo = result.scalar_one_or_none()
        if not vinculo:
            raise HTTPException(status_code=404, detail="El usuario no está vinculado a esta estación.")
        if vinculo.rol == "owner":
            raise HTTPException(status_code=400, detail="No se puede quitar al dueño de la estación.")

        await db.delete(vinculo)
        await db.commit()

    # ------------------------------------------------------------------
    # ADMIN: bloquear / desbloquear usuario (por código)
    # ------------------------------------------------------------------
    @staticmethod
    async def admin_block_user(db: AsyncSession, admin: User, codigo: str, target_user_id: int, blocked: bool):
        if admin.role not in (UserRole.admin, UserRole.superadmin):
            raise HTTPException(status_code=403, detail="Solo un admin puede bloquear usuarios.")

        estacion = await StationService._get_estacion_by_codigo(db, codigo)

        result = await db.execute(
            select(EstacionUsuario).where(
                EstacionUsuario.user_id == target_user_id,
                EstacionUsuario.estacion_id == estacion.id
            )
        )
        vinculo = result.scalar_one_or_none()
        if not vinculo:
            raise HTTPException(status_code=404, detail="El usuario no está vinculado a esta estación.")
        if vinculo.rol == "owner":
            raise HTTPException(status_code=400, detail="No se puede bloquear al dueño.")

        vinculo.is_blocked = blocked
        vinculo.blocked_at = datetime.utcnow() if blocked else None

        await db.commit()
        await db.refresh(vinculo)
        return vinculo

    @staticmethod
    async def get_rain_last_12h(db: AsyncSession, user: User, codigo: str):
        estacion = await StationService._get_estacion_by_codigo(db, codigo)

        # (opcional) validar que el usuario tenga acceso a esta estación
        if not estacion.is_public:
            result = await db.execute(
                select(EstacionUsuario).where(
                    EstacionUsuario.user_id == user.id,
                    EstacionUsuario.estacion_id == estacion.id,
                    EstacionUsuario.is_blocked == False
                )
            )
            vinculo = result.scalar_one_or_none()
            if not vinculo:
                raise HTTPException(status_code=403, detail="No tienes acceso a esta estación.")

        weatherService = WeatherService(db)
        return await weatherService.get_last_12h_rain(codigo)