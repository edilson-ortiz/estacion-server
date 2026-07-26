from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, extract, func, cast, Date
from app.models.Estacion import SensorData, Estacion, CalibracionPluviometro
from datetime import datetime, timedelta, timezone
from bisect import bisect_right


class WeatherService:

    def __init__(self, db: AsyncSession):
        self.db = db

    # ─────────────────────────────────────────────────────────────
    # Carga TODOS los factores de una estación de una sola query
    # Retorna lista ordenada lista para búsqueda binaria en memoria
    # ─────────────────────────────────────────────────────────────
    async def _load_factores(self, sensor_id: str) -> list[tuple[datetime, float]]:
        """
        Retorna lista de (vigente_desde, factor_k) ordenada por fecha ASC.
        Se usa con bisect para encontrar el factor vigente en O(log n).
        """
        result = await self.db.execute(
            select(
                CalibracionPluviometro.vigente_desde,
                CalibracionPluviometro.factor_k
            )
            .where(CalibracionPluviometro.estacion_codigo == sensor_id)
            .order_by(CalibracionPluviometro.vigente_desde.asc())
        )
        return result.all()  # [(vigente_desde, factor_k), ...]

    def _factor_en_fecha(self, factores: list, fecha: datetime) -> float:
        """
        Búsqueda binaria en memoria: O(log n) en lugar de query a BD.
        Retorna el factor_k vigente para la fecha dada.
        """
        if not factores:
            return 0.1

        fechas = [f[0] for f in factores]

        # Asegurar timezone para comparar
        if fecha.tzinfo is None:
            fecha = fecha.replace(tzinfo=timezone.utc)

        fechas_aware = [
            f.replace(tzinfo=timezone.utc) if f.tzinfo is None else f
            for f in fechas
        ]

        idx = bisect_right(fechas_aware, fecha) - 1

        if idx < 0:
            return 0.1  # fecha anterior a toda calibración, fallback

        return factores[idx][1]

    # ─────────────────────────────────────────────────────────────
    # Factor vigente — para uso en métodos que solo necesitan 1 fecha
    # ─────────────────────────────────────────────────────────────
    async def _get_factor_k(self, sensor_id: str, fecha: datetime) -> float:
        factores = await self._load_factores(sensor_id)
        return self._factor_en_fecha(factores, fecha)

    async def get_latest_record(self, sensor_id: str):

        result = await self.db.execute(
            select(Estacion).where(Estacion.codigo == sensor_id)
        )
        estacion = result.scalar_one_or_none()

        if not estacion:
            return None

        result = await self.db.execute(
            select(SensorData)
            .where(SensorData.sensor_id == estacion.codigo)
            .order_by(SensorData.fecha.desc())
            .limit(1)
        )
        record = result.scalar_one_or_none()

        if not record:
            datos = None
            estacion_activa = False
        else:
            now = datetime.now(timezone.utc)
            diferencia = now - record.fecha
            estacion_activa = diferencia <= timedelta(hours=1)

            # Una sola query para todos los factores
            factores = await self._load_factores(sensor_id)

            BOLIVIA_OFFSET = timedelta(hours=4)
            now_bolivia = now - BOLIVIA_OFFSET
            inicio_dia_bolivia = datetime(
                now_bolivia.year, now_bolivia.month, now_bolivia.day,
                tzinfo=timezone.utc
            ) + BOLIVIA_OFFSET

            factor_k = self._factor_en_fecha(factores, now)

            result = await self.db.execute(
                select(func.sum(SensorData.lluvia))
                .where(
                    SensorData.sensor_id == estacion.codigo,
                    SensorData.fecha >= inicio_dia_bolivia,
                    SensorData.fecha <= now
                )
            )
            acumulado_hoy = (result.scalar() or 0.0) * factor_k

            ayer_inicio = inicio_dia_bolivia - timedelta(days=1)
            ayer_fin = inicio_dia_bolivia
            factor_k_ayer = self._factor_en_fecha(factores, ayer_inicio)

            result = await self.db.execute(
                select(func.sum(SensorData.lluvia))
                .where(
                    SensorData.sensor_id == estacion.codigo,
                    SensorData.fecha >= ayer_inicio,
                    SensorData.fecha < ayer_fin
                )
            )
            acumulado_ayer = (result.scalar() or 0.0) * factor_k_ayer

            factor_k_record = self._factor_en_fecha(factores, record.fecha)

            datos = {
                "id": record.id,
                "temperatura": record.temperatura,
                "humedad": record.humedad,
                "punto_rocio": round(record.temperatura - ((100 - record.humedad) / 5), 1),
                "lluvia": round(record.lluvia * factor_k_record, 1),
                "lluvia_hoy": round(acumulado_hoy, 1),
                "lluvia_ayer": round(acumulado_ayer, 1),
                "velocidad_viento": record.velocidad_viento,
                "direccion_viento": record.direccion_viento,
                "direccion_viento_texto": self.direccion_viento_texto(record.direccion_viento),
                "rafaga_viento": record.rafaga_viento,
                "presion_barometrica": record.presion_barometrica,
                "estado": estacion_activa,
                "fecha": record.fecha.isoformat(sep=' ')
            }

        return {
            "codigo": estacion.codigo,
            "nombre": estacion.nombre,
            "modelo": estacion.modelo,
            "ubicacion": estacion.ubicacion,
            "latitud": estacion.latitud,
            "longitud": estacion.longitud,
            "descripcion": estacion.descripcion,
            "datos": datos
        }

    def direccion_viento_texto(self, direccion_grados: float):
        if direccion_grados is None:
            return "N/A"
        direcciones = ["N", "NE", "E", "SE", "S", "SO", "O", "NO"]
        indice = round(direccion_grados / 45) % 8
        return direcciones[indice]

    async def get_daily_summary(self, sensor_id: str, days: int = 30):

        desde = datetime.now(timezone.utc) - timedelta(days=days)

        result = await self.db.execute(
            select(
                SensorData.fecha,
                SensorData.temperatura,
                SensorData.humedad,
                SensorData.lluvia
            ).where(
                SensorData.sensor_id == sensor_id,
                SensorData.fecha >= desde
            )
        )
        records = result.mappings().all()

        if not records:
            return []

        # Una sola query de factores para todos los registros
        factores = await self._load_factores(sensor_id)

        resumen = {}
        for r in records:
            dia = r["fecha"].date()
            factor_k = self._factor_en_fecha(factores, r["fecha"])

            if dia not in resumen:
                resumen[dia] = {
                    "total_lluvia": 0,
                    "temp_min": r["temperatura"],
                    "temp_max": r["temperatura"],
                    "humedad_max": r["humedad"]
                }

            resumen[dia]["total_lluvia"] += r["lluvia"] * factor_k
            resumen[dia]["temp_min"] = min(resumen[dia]["temp_min"], r["temperatura"])
            resumen[dia]["temp_max"] = max(resumen[dia]["temp_max"], r["temperatura"])
            resumen[dia]["humedad_max"] = max(resumen[dia]["humedad_max"], r["humedad"])

        return [
            {
                "dia": dia.isoformat(),
                "total_lluvia": round(d["total_lluvia"], 2),
                "temp_min": d["temp_min"],
                "temp_max": d["temp_max"],
                "humedad": d["humedad_max"]
            }
            for dia, d in sorted(resumen.items(), reverse=True)
        ]

    async def get_monthly_daily_rain(self, sensor_id: str, year: int, month: int):

        result = await self.db.execute(
            select(SensorData.fecha, SensorData.lluvia)
            .where(
                SensorData.sensor_id == sensor_id,
                extract("year", SensorData.fecha) == year,
                extract("month", SensorData.fecha) == month
            )
            .order_by(SensorData.fecha)
        )
        rows = result.mappings().all()

        if not rows:
            return []

        # Una sola query de factores
        factores = await self._load_factores(sensor_id)

        resumen = {}
        for r in rows:
            dia = r["fecha"].date()
            factor_k = self._factor_en_fecha(factores, r["fecha"])
            resumen[dia] = resumen.get(dia, 0.0) + r["lluvia"] * factor_k

        return [
            {
                "fecha": dia.isoformat(),
                "suma_lluvia": round(suma, 2)
            }
            for dia, suma in sorted(resumen.items())
        ]

    

    async def get_year_daily_rain(self, sensor_id: str, year: int):
        """
        Optimizado:
        - 1 query para los datos del año (agrupado por día en SQL)
        - 1 query para todos los factores de calibración
        - Búsqueda del factor en memoria con bisect O(log n)
        - Sin loops de queries a BD
        """
        fecha_bolivia = func.timezone('America/La_Paz', SensorData.fecha)

        # Query agrupada en SQL — trae solo 365 filas máximo
        result = await self.db.execute(
            select(
                func.date(fecha_bolivia).label("dia"),
                func.sum(SensorData.lluvia).label("suma_lluvia")
            )
            .where(
                SensorData.sensor_id == sensor_id,
                extract("year", fecha_bolivia) == year
            )
            .group_by(func.date(fecha_bolivia))
            .order_by(func.date(fecha_bolivia))
        )
        rows = result.all()

        if not rows:
            return []

        # Una sola query para todos los factores
        factores = await self._load_factores(sensor_id)

        return [
            {
                "fecha": r.dia.isoformat(),
                # El día agrupado está en Bolivia, lo convertimos a UTC para buscar el factor
                "suma_lluvia": round(
                    float(r.suma_lluvia) * self._factor_en_fecha(
                        factores,
                        datetime(r.dia.year, r.dia.month, r.dia.day, tzinfo=timezone.utc)
                    ),
                    2
                )
            }
            for r in rows
        ]

    async def get_rain_sum_between_dates(self, sensor_id: str, start_date: datetime, end_date: datetime):

        result = await self.db.execute(
            select(SensorData.fecha, SensorData.lluvia)
            .where(
                SensorData.sensor_id == sensor_id,
                cast(SensorData.fecha, Date) >= start_date.date(),
                cast(SensorData.fecha, Date) <= end_date.date()
            )
        )
        rows = result.mappings().all()

        if not rows:
            return 0.0

        # Una sola query de factores
        factores = await self._load_factores(sensor_id)

        total = sum(r["lluvia"] * self._factor_en_fecha(factores, r["fecha"]) for r in rows)
        return round(total, 2)
    async def get_last_12h_rain(self, sensor_id: str):
        """
        Retorna:
        - Precipitación acumulada de cada una de las últimas 12 horas (para gráfico)
        - Acumulado de hoy y ayer
        - Temperatura y humedad máxima/mínima del día (hora Bolivia)
        """
        now = datetime.now(timezone.utc)
        desde = now - timedelta(hours=12)

        result = await self.db.execute(
            select(SensorData.fecha, SensorData.lluvia)
            .where(
                SensorData.sensor_id == sensor_id,
                SensorData.fecha >= desde,
                SensorData.fecha <= now
            )
            .order_by(SensorData.fecha)
        )
        rows = result.mappings().all()

        # Una sola query de factores, reusada para todo el método
        factores = await self._load_factores(sensor_id)

        # ---------------- Buckets por hora (gráfico 12h) ----------------
        hora_actual = now.replace(minute=0, second=0, microsecond=0)
        buckets = {
            hora_actual - timedelta(hours=i): 0.0
            for i in range(11, -1, -1)
        }

        for r in rows:
            fecha = r["fecha"]
            if fecha.tzinfo is None:
                fecha = fecha.replace(tzinfo=timezone.utc)

            hora_bucket = fecha.replace(minute=0, second=0, microsecond=0)

            if hora_bucket in buckets:
                factor_k = self._factor_en_fecha(factores, fecha)
                buckets[hora_bucket] += r["lluvia"] * factor_k

        BOLIVIA_OFFSET = timedelta(hours=4)

        # ---------------- Límites del día actual y de ayer, en hora Bolivia ----------------
        now_bolivia = now - BOLIVIA_OFFSET
        inicio_dia_bolivia = datetime(
            now_bolivia.year, now_bolivia.month, now_bolivia.day,
            tzinfo=timezone.utc
        ) + BOLIVIA_OFFSET

        ayer_inicio = inicio_dia_bolivia - timedelta(days=1)
        ayer_fin = inicio_dia_bolivia

        # ---------------- Acumulado de lluvia hoy ----------------
        factor_k_hoy = self._factor_en_fecha(factores, now)
        result = await self.db.execute(
            select(func.sum(SensorData.lluvia))
            .where(
                SensorData.sensor_id == sensor_id,
                SensorData.fecha >= inicio_dia_bolivia,
                SensorData.fecha <= now
            )
        )
        acumulado_hoy = (result.scalar() or 0.0) * factor_k_hoy

        # ---------------- Acumulado de lluvia ayer ----------------
        factor_k_ayer = self._factor_en_fecha(factores, ayer_inicio)
        result = await self.db.execute(
            select(func.sum(SensorData.lluvia))
            .where(
                SensorData.sensor_id == sensor_id,
                SensorData.fecha >= ayer_inicio,
                SensorData.fecha < ayer_fin
            )
        )
        acumulado_ayer = (result.scalar() or 0.0) * factor_k_ayer

        # ---------------- Temp y humedad max/min de HOY (mismo rango que la lluvia de hoy) ----------------
        result_stats = await self.db.execute(
            select(
                func.max(SensorData.temperatura).label("temp_max"),
                func.min(SensorData.temperatura).label("temp_min"),
                func.max(SensorData.humedad).label("humedad_max"),
                func.min(SensorData.humedad).label("humedad_min"),
            )
            .where(
                SensorData.sensor_id == sensor_id,
                SensorData.fecha >= inicio_dia_bolivia,
                SensorData.fecha <= now
            )
        )
        stats_dia = result_stats.one()

        # ---------------- Armado del gráfico 12h ----------------
        rain_12h = [
            {
                "hora": (hora - BOLIVIA_OFFSET).strftime("%H:00"),
                "fecha_hora": (hora - BOLIVIA_OFFSET).isoformat(),
                "lluvia": round(valor, 2)
            }
            for hora, valor in buckets.items()
        ]

        return {
            "rain_12h": rain_12h,
            "acumulado_hoy": round(acumulado_hoy, 2),
            "acumulado_ayer": round(acumulado_ayer, 2),
            "temp_max": stats_dia.temp_max,
            "temp_min": stats_dia.temp_min,
            "humedad_max": stats_dia.humedad_max,
            "humedad_min": stats_dia.humedad_min,
        }

    async def get_latest_record_pro(self, sensor_id: str):
    
            result = await self.db.execute(
                select(Estacion).where(Estacion.codigo == sensor_id)
            )
            estacion = result.scalar_one_or_none()
    
            if not estacion:
                return None
    
            result = await self.db.execute(
                select(SensorData)
                .where(SensorData.sensor_id == estacion.codigo)
                .order_by(SensorData.fecha.desc())
                .limit(1)
            )
            record = result.scalar_one_or_none()
    
            if not record:
                datos = None
                estacion_activa = False
            else:
                now = datetime.now(timezone.utc)
                diferencia = now - record.fecha
                estacion_activa = diferencia <= timedelta(hours=1)
    
                # Una sola query para todos los factores
                factores = await self._load_factores(sensor_id)
    
                BOLIVIA_OFFSET = timedelta(hours=4)
                now_bolivia = now - BOLIVIA_OFFSET
                inicio_dia_bolivia = datetime(
                    now_bolivia.year, now_bolivia.month, now_bolivia.day,
                    tzinfo=timezone.utc
                ) + BOLIVIA_OFFSET
    
    
                factor_k_record = self._factor_en_fecha(factores, record.fecha)
    
                datos = {
                    "id": record.id,
                    "temperatura": record.temperatura,
                    "humedad": record.humedad,
                    "punto_rocio": round(record.temperatura - ((100 - record.humedad) / 5), 1),
                    "lluvia": round(record.lluvia * factor_k_record, 1),
                    "velocidad_viento": record.velocidad_viento,
                    "direccion_viento": record.direccion_viento,
                    "direccion_viento_texto": self.direccion_viento_texto(record.direccion_viento),
                    "rafaga_viento": record.rafaga_viento,
                    "presion_barometrica": record.presion_barometrica,
                    "estado": estacion_activa,
                    "fecha": record.fecha.isoformat(sep=' ')
                }
    
            return {
                "datos": datos
            }
    