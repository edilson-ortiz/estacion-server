"""Consultas de datos meteorológicos de las estaciones.

La lluvia en BD está en pulsos crudos; siempre se convierte a mm con el factor de
calibración vigente (ver services/calibracion.py). Los agregados se calculan en SQL.
"""
from __future__ import annotations

from collections.abc import Iterable
from datetime import date, datetime, timedelta, timezone

from sqlalchemy import DateTime, and_, cast, func, literal, select, true
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import aliased

from app.core.time import (
    BOLIVIA_OFFSET,
    BOLIVIA_TZ_NAME,
    STATION_ACTIVE_WINDOW,
    ensure_aware,
    inicio_dia_bolivia,
    utcnow,
)
from app.models import Estacion, SensorData
from app.services.calibracion import Calibracion, load_calibracion, load_calibraciones

_DIRECCIONES = ["N", "NE", "E", "SE", "S", "SO", "O", "NO"]


def direccion_viento_texto(direccion_grados: float | None) -> str:
    if direccion_grados is None:
        return "N/A"
    return _DIRECCIONES[round(direccion_grados / 45) % 8]


def _punto_rocio(temperatura: float | None, humedad: float | None) -> float | None:
    if temperatura is None or humedad is None:
        return None
    return round(temperatura - ((100 - humedad) / 5), 1)


def _format_datos(
    record: SensorData,
    calibracion: Calibracion,
    now: datetime,
    acumulados: dict | None = None,
) -> dict:
    """Arma el bloque "datos" de una estación a partir de su último registro."""
    lluvia = record.lluvia
    datos = {
        "id": record.id,
        "temperatura": record.temperatura,
        "humedad": record.humedad,
        "punto_rocio": _punto_rocio(record.temperatura, record.humedad),
        "lluvia": round(lluvia * calibracion.factor_en(record.fecha), 1) if lluvia is not None else None,
    }
    if acumulados:
        datos.update(acumulados)
    datos.update({
        "velocidad_viento": record.velocidad_viento,
        "direccion_viento": record.direccion_viento,
        "direccion_viento_texto": direccion_viento_texto(record.direccion_viento),
        "rafaga_viento": record.rafaga_viento,
        "presion_barometrica": record.presion_barometrica,
        "estado": now - record.fecha <= STATION_ACTIVE_WINDOW,
        "fecha": record.fecha.isoformat(sep=" "),
    })
    return datos


class WeatherService:

    def __init__(self, db: AsyncSession):
        self.db = db

    # ------------------------------------------------------------------
    # Helpers de consulta
    # ------------------------------------------------------------------
    async def _get_last_record(self, sensor_id: str) -> SensorData | None:
        result = await self.db.execute(
            select(SensorData)
            .where(SensorData.sensor_id == sensor_id)
            .order_by(SensorData.fecha.desc())
            .limit(1)
        )
        return result.scalar_one_or_none()

    async def _get_last_records(self, codigos: list[str]) -> dict[str, SensorData]:
        """Último registro de cada estación en UNA consulta (LATERAL + índice sensor_id, fecha)."""
        sub = (
            select(SensorData)
            .where(SensorData.sensor_id == Estacion.codigo)
            .order_by(SensorData.fecha.desc())
            .limit(1)
            .lateral()
        )
        ultimo = aliased(SensorData, sub)
        result = await self.db.execute(
            select(ultimo)
            .select_from(Estacion)
            .join(sub, true())
            .where(Estacion.codigo.in_(codigos))
        )
        return {r.sensor_id: r for r in result.scalars()}

    def _resumen_hoy_ayer(self, sensor_id: str, now: datetime, **extra_hoy):
        """SELECT con la lluvia (cruda) de hoy y de ayer en hora Bolivia, más agregados extra de hoy.

        extra_hoy: nombre=func.max(...) etc.; se calculan solo sobre las filas de hoy.
        """
        inicio_hoy = inicio_dia_bolivia(now)
        inicio_ayer = inicio_hoy - timedelta(days=1)
        hoy = and_(SensorData.fecha >= inicio_hoy, SensorData.fecha <= now)
        ayer = and_(SensorData.fecha >= inicio_ayer, SensorData.fecha < inicio_hoy)
        stmt = select(
            func.sum(SensorData.lluvia).filter(hoy).label("lluvia_hoy"),
            func.sum(SensorData.lluvia).filter(ayer).label("lluvia_ayer"),
            *(agg.filter(hoy).label(nombre) for nombre, agg in extra_hoy.items()),
        ).where(
            SensorData.sensor_id == sensor_id,
            SensorData.fecha >= inicio_ayer,
            SensorData.fecha <= now,
        )
        return stmt, inicio_ayer

    # ------------------------------------------------------------------
    # Último registro de una estación (con acumulados de hoy/ayer)
    # ------------------------------------------------------------------
    async def get_latest_record(self, sensor_id: str) -> dict | None:
        result = await self.db.execute(select(Estacion).where(Estacion.codigo == sensor_id))
        estacion = result.scalar_one_or_none()
        if not estacion:
            return None

        record = await self._get_last_record(sensor_id)
        datos = None
        if record:
            now = utcnow()
            calibracion = await load_calibracion(self.db, sensor_id)
            stmt, inicio_ayer = self._resumen_hoy_ayer(sensor_id, now)
            fila = (await self.db.execute(stmt)).one()

            datos = _format_datos(record, calibracion, now, {
                "lluvia_hoy": round((fila.lluvia_hoy or 0.0) * calibracion.factor_en(now), 1),
                "lluvia_ayer": round((fila.lluvia_ayer or 0.0) * calibracion.factor_en(inicio_ayer), 1),
            })

        return {
            "codigo": estacion.codigo,
            "nombre": estacion.nombre,
            "modelo": estacion.modelo,
            "ubicacion": estacion.ubicacion,
            "latitud": estacion.latitud,
            "longitud": estacion.longitud,
            "descripcion": estacion.descripcion,
            "datos": datos,
        }

    # ------------------------------------------------------------------
    # Último registro de varias estaciones (listado de estaciones)
    # ------------------------------------------------------------------
    async def get_latest_datos_many(self, codigos: Iterable[str]) -> dict[str, dict | None]:
        """{codigo: datos | None}. Siempre 2 consultas, sin importar cuántas estaciones sean."""
        codigos = list(set(codigos))
        if not codigos:
            return {}
        records = await self._get_last_records(codigos)
        calibraciones = await load_calibraciones(self.db, records.keys())
        now = utcnow()
        return {
            codigo: _format_datos(records[codigo], calibraciones[codigo], now)
            if codigo in records else None
            for codigo in codigos
        }

    # ------------------------------------------------------------------
    # Resumen diario de los últimos N días
    # ------------------------------------------------------------------
    async def get_daily_summary(self, sensor_id: str, days: int = 30) -> list[dict]:
        desde = utcnow() - timedelta(days=days)
        calibracion = await load_calibracion(self.db, sensor_id)
        dia = func.date(SensorData.fecha)

        result = await self.db.execute(
            select(
                dia.label("dia"),
                func.sum(SensorData.lluvia * calibracion.factor_sql(SensorData.fecha)).label("total_lluvia"),
                func.min(SensorData.temperatura).label("temp_min"),
                func.max(SensorData.temperatura).label("temp_max"),
                func.max(SensorData.humedad).label("humedad_max"),
            )
            .where(SensorData.sensor_id == sensor_id, SensorData.fecha >= desde)
            .group_by(dia)
            .order_by(dia.desc())
        )
        return [
            {
                "dia": r.dia.isoformat(),
                "total_lluvia": round(r.total_lluvia or 0.0, 2),
                "temp_min": r.temp_min,
                "temp_max": r.temp_max,
                "humedad": r.humedad_max,
            }
            for r in result
        ]

    # ------------------------------------------------------------------
    # Lluvia diaria de un mes
    # ------------------------------------------------------------------
    async def get_monthly_daily_rain(self, sensor_id: str, year: int, month: int) -> list[dict]:
        if not (1 <= month <= 12 and 1 <= year <= 9998):
            return []
        desde = date(year, month, 1)
        hasta = date(year + month // 12, month % 12 + 1, 1)
        return await self._lluvia_por_dia(sensor_id, desde, hasta)

    async def _lluvia_por_dia(self, sensor_id: str, desde: date, hasta: date) -> list[dict]:
        """Lluvia diaria en [desde, hasta). Las fechas se interpretan en la zona horaria de la sesión de BD."""
        calibracion = await load_calibracion(self.db, sensor_id)
        dia = func.date(SensorData.fecha)
        result = await self.db.execute(
            select(
                dia.label("dia"),
                func.sum(SensorData.lluvia * calibracion.factor_sql(SensorData.fecha)).label("suma"),
            )
            .where(
                SensorData.sensor_id == sensor_id,
                SensorData.fecha >= desde,
                SensorData.fecha < hasta,
            )
            .group_by(dia)
            .order_by(dia)
        )
        return [{"fecha": r.dia.isoformat(), "suma_lluvia": round(r.suma or 0.0, 2)} for r in result]

    # ------------------------------------------------------------------
    # Lluvia diaria de un año (días en hora Bolivia)
    # ------------------------------------------------------------------
    async def get_year_daily_rain(self, sensor_id: str, year: int) -> list[dict]:
        if not 1 <= year <= 9998:
            return []

        def inicio_anio_bolivia(y: int):
            return func.timezone(BOLIVIA_TZ_NAME, cast(literal(datetime(y, 1, 1)), DateTime()))

        dia = func.date(func.timezone(BOLIVIA_TZ_NAME, SensorData.fecha))
        result = await self.db.execute(
            select(dia.label("dia"), func.sum(SensorData.lluvia).label("suma_lluvia"))
            .where(
                SensorData.sensor_id == sensor_id,
                SensorData.fecha >= inicio_anio_bolivia(year),
                SensorData.fecha < inicio_anio_bolivia(year + 1),
            )
            .group_by(dia)
            .order_by(dia)
        )
        rows = result.all()
        if not rows:
            return []

        calibracion = await load_calibracion(self.db, sensor_id)
        return [
            {
                "fecha": r.dia.isoformat(),
                # Factor vigente al inicio del día (en UTC)
                "suma_lluvia": round(
                    float(r.suma_lluvia or 0.0)
                    * calibracion.factor_en(datetime(r.dia.year, r.dia.month, r.dia.day, tzinfo=timezone.utc)),
                    2,
                ),
            }
            for r in rows
        ]

    # ------------------------------------------------------------------
    # Lluvia total entre dos fechas (inclusive)
    # ------------------------------------------------------------------
    async def get_rain_sum_between_dates(
        self, sensor_id: str, start_date: datetime, end_date: datetime
    ) -> float:
        calibracion = await load_calibracion(self.db, sensor_id)
        condiciones = [SensorData.sensor_id == sensor_id, SensorData.fecha >= start_date.date()]
        if end_date.date() < date.max:
            condiciones.append(SensorData.fecha < end_date.date() + timedelta(days=1))

        result = await self.db.execute(
            select(func.sum(SensorData.lluvia * calibracion.factor_sql(SensorData.fecha))).where(*condiciones)
        )
        total = result.scalar()
        return round(total, 2) if total is not None else 0.0

    # ------------------------------------------------------------------
    # Lluvia por hora de las últimas 12h + resumen del día
    # ------------------------------------------------------------------
    async def get_last_12h_rain(self, sensor_id: str) -> dict:
        now = utcnow()
        calibracion = await load_calibracion(self.db, sensor_id)

        # ---------------- Buckets por hora (gráfico 12h) ----------------
        result = await self.db.execute(
            select(SensorData.fecha, SensorData.lluvia).where(
                SensorData.sensor_id == sensor_id,
                SensorData.fecha >= now - timedelta(hours=12),
                SensorData.fecha <= now,
            )
        )
        hora_actual = now.replace(minute=0, second=0, microsecond=0)
        buckets = {hora_actual - timedelta(hours=i): 0.0 for i in range(11, -1, -1)}
        for fecha, lluvia in result:
            fecha = ensure_aware(fecha)
            hora = fecha.replace(minute=0, second=0, microsecond=0)
            if hora in buckets and lluvia is not None:
                buckets[hora] += lluvia * calibracion.factor_en(fecha)

        # ---------------- Lluvia hoy/ayer + temp/humedad de hoy (1 consulta) ----------------
        stmt, inicio_ayer = self._resumen_hoy_ayer(
            sensor_id,
            now,
            temp_max=func.max(SensorData.temperatura),
            temp_min=func.min(SensorData.temperatura),
            humedad_max=func.max(SensorData.humedad),
            humedad_min=func.min(SensorData.humedad),
        )
        fila = (await self.db.execute(stmt)).one()

        return {
            "rain_12h": [
                {
                    "hora": (hora - BOLIVIA_OFFSET).strftime("%H:00"),
                    "fecha_hora": (hora - BOLIVIA_OFFSET).isoformat(),
                    "lluvia": round(valor, 2),
                }
                for hora, valor in buckets.items()
            ],
            "acumulado_hoy": round((fila.lluvia_hoy or 0.0) * calibracion.factor_en(now), 2),
            "acumulado_ayer": round((fila.lluvia_ayer or 0.0) * calibracion.factor_en(inicio_ayer), 2),
            "temp_max": fila.temp_max,
            "temp_min": fila.temp_min,
            "humedad_max": fila.humedad_max,
            "humedad_min": fila.humedad_min,
        }
