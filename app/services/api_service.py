from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, extract, func, cast, Date
from app.models.Estacion import SensorData, Estacion
from datetime import datetime, timedelta, timezone


class ApiService:

    def __init__(self, db: AsyncSession):
        self.db = db
        self.kmilimetro = 10

    async def get_latest_record(self, sensor_id: str):

        # Buscar estación
        result = await self.db.execute(
            select(Estacion).where(Estacion.codigo == sensor_id)
        )
        estacion = result.scalar_one_or_none()

        if not estacion:
            return None

        # Último registro
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

            inicio_dia = datetime(now.year, now.month, now.day, tzinfo=timezone.utc)

            # lluvia hoy
            result = await self.db.execute(
                select(func.sum(SensorData.lluvia))
                .where(
                    SensorData.sensor_id == estacion.codigo,
                    SensorData.fecha >= inicio_dia,
                    SensorData.fecha <= now
                )
            )

            acumulado_hoy = result.scalar() or 0.0
            acumulado_hoy = acumulado_hoy / self.kmilimetro

            # lluvia ayer
            ayer_inicio = inicio_dia - timedelta(days=1)
            ayer_fin = inicio_dia

            result = await self.db.execute(
                select(func.sum(SensorData.lluvia))
                .where(
                    SensorData.sensor_id == estacion.codigo,
                    SensorData.fecha >= ayer_inicio,
                    SensorData.fecha < ayer_fin
                )
            )

            acumulado_ayer = result.scalar() or 0.0
            acumulado_ayer = acumulado_ayer / self.kmilimetro

            return {
                "id": record.id,
                "temperatura": record.temperatura,
                "humedad": record.humedad,
                "punto_rocio": round(record.temperatura - ((100 - record.humedad) / 5), 1),
                "lluvia": record.lluvia / self.kmilimetro,
                "lluvia_hoy": acumulado_hoy,
                "lluvia_ayer": acumulado_ayer,
                "velocidad_viento": record.velocidad_viento,
                "direccion_viento": record.direccion_viento,
                "direccion_viento_texto": self.direccion_viento_texto(record.direccion_viento),
                "rafaga_viento": record.rafaga_viento,
                "presion_barometrica": record.presion_barometrica,
                "estado": estacion_activa,
                "fecha": record.fecha.isoformat(sep=' ')
            }

    def direccion_viento_texto(self, direccion_grados: float):

        if direccion_grados is None:
            return "N/A"

        direcciones = ["N", "NE", "E", "SE", "S", "SO", "O", "NO"]
        indice = round(direccion_grados / 45) % 8

        return direcciones[indice]

    async def get_daily_summary(self, sensor_id: str, days: int = 30):

        desde = datetime.now() - timedelta(days=days)

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

        resumen = {}

        for r in records:

            dia = r["fecha"].date()

            if dia not in resumen:
                resumen[dia] = {
                    "total_lluvia": 0,
                    "temp_min": r["temperatura"],
                    "temp_max": r["temperatura"],
                    "humedad_max": r["humedad"]
                }

            resumen[dia]["total_lluvia"] += r["lluvia"]
            resumen[dia]["temp_min"] = min(resumen[dia]["temp_min"], r["temperatura"])
            resumen[dia]["temp_max"] = max(resumen[dia]["temp_max"], r["temperatura"])
            resumen[dia]["humedad_max"] = max(resumen[dia]["humedad_max"], r["humedad"])

        return [
            {
                "dia": dia.isoformat(),
                "total_lluvia": round(d["total_lluvia"]/self.kmilimetro, 2),
                "temp_min": d["temp_min"],
                "temp_max": d["temp_max"],
                "humedad": d["humedad_max"]
            }
            for dia, d in sorted(resumen.items(), reverse=True)
        ]

    async def get_monthly_daily_rain(self, sensor_id: str, year: int, month: int):

        result = await self.db.execute(
            select(
                func.date(SensorData.fecha).label("dia"),
                func.sum(SensorData.lluvia).label("suma_lluvia")
            )
            .where(
                SensorData.sensor_id == sensor_id,
                extract("year", SensorData.fecha) == year,
                extract("month", SensorData.fecha) == month
            )
            .group_by(func.date(SensorData.fecha))
            .order_by(func.date(SensorData.fecha))
        )

        rows = result.all()

        return [
            {
                "fecha": r.dia.isoformat(),
                "suma_lluvia": float(r.suma_lluvia)/self.kmilimetro
            }
            for r in rows
        ]

    async def get_year_daily_rain(self, sensor_id: str, year: int):

        result = await self.db.execute(
            select(
                func.date(SensorData.fecha).label("dia"),
                func.sum(SensorData.lluvia).label("suma_lluvia")
            )
            .where(
                SensorData.sensor_id == sensor_id,
                extract("year", SensorData.fecha) == year
            )
            .group_by(func.date(SensorData.fecha))
            .order_by(func.date(SensorData.fecha))
        )

        rows = result.all()

        return [
            {
                "fecha": r.dia.isoformat(),
                "suma_lluvia": float(r.suma_lluvia)/self.kmilimetro
            }
            for r in rows
        ]

    async def get_rain_sum_between_dates(self, sensor_id: str, start_date: datetime, end_date: datetime):

        result = await self.db.execute(
            select(func.sum(SensorData.lluvia))
            .where(
                SensorData.sensor_id == sensor_id,
                cast(SensorData.fecha, Date) >= start_date.date(),
                cast(SensorData.fecha, Date) <= end_date.date()
            )
        )

        suma_lluvia = result.scalar()

        return (suma_lluvia or 0.0) / self.kmilimetro