from sqlalchemy.orm import Session
from sqlalchemy import extract, func,cast, Date
from app.models.sensor_data import SensorData
from app.models.sensor_data import Estacion
from datetime import date
from datetime import datetime, timedelta, timezone


class WeatherService:
    def __init__(self, db: Session):
        self.db = db
        self.kmilimetro = 10

    def get_latest_record(self, sensor_id: str):
        # Buscar la estación primero
        estacion = (
            self.db.query(Estacion)
            .filter(Estacion.codigo == sensor_id)
            .first()
        )

        if not estacion:
            return None

        # Traer el último registro asociado a esa estación
        record = (
            self.db.query(SensorData)
            .filter(SensorData.sensor_id == estacion.codigo)
            .order_by(SensorData.fecha.desc())
            .first()
        )

        if not record:
            datos = None
            estacion_activa = False
        else:
            # Calcular diferencia de tiempo
            now = datetime.now(timezone.utc)
            diferencia = now - record.fecha
            estacion_activa = diferencia <= timedelta(hours=1)

            # Hora actual
            now = datetime.now(timezone.utc)

            # Inicio del día (medianoche) en UTC
            inicio_dia = datetime(now.year, now.month, now.day, tzinfo=timezone.utc)

            # Lluvia acumulada desde medianoche hasta ahora
            acumulado_hoy = (
                self.db.query(func.sum(SensorData.lluvia))
                .filter(
                    SensorData.sensor_id == estacion.codigo,
                    SensorData.fecha >= inicio_dia,
                    SensorData.fecha <= now
                )
                .scalar()
            )
            acumulado_hoy = (acumulado_hoy or 0.0) / self.kmilimetro

            ayer_inicio = datetime(now.year, now.month, now.day, tzinfo=timezone.utc) - timedelta(days=1)
            ayer_fin = ayer_inicio + timedelta(days=1)

            acumulado_ayer = (
                self.db.query(func.sum(SensorData.lluvia))
                .filter(
                    SensorData.sensor_id == estacion.codigo,
                    SensorData.fecha >= ayer_inicio,
                    SensorData.fecha < ayer_fin
                )
                .scalar()
            )
            acumulado_ayer = (acumulado_ayer or 0.0) / self.kmilimetro



            datos = {
                "id": record.id,
                "temperatura": record.temperatura,
                "humedad": record.humedad,
                "punto_rocio": round(record.temperatura - ((100 - record.humedad) / 5), 1),
                "lluvia": record.lluvia / self.kmilimetro,
                "lluvia_hoy": acumulado_hoy,  # ahora contiene última hora
                "lluvia_ayer": acumulado_ayer,

                "velocidad_viento": record.velocidad_viento,
                "direccion_viento": record.direccion_viento,
                "direccion_viento_texto": self.direccion_viento_texto(record.direccion_viento),
                "rafaga_viento": record.rafaga_viento,
                "presion_barometrica": record.presion_barometrica,
            
                "estado": estacion_activa,
                "fecha": record.fecha.isoformat(sep=' ')
            }

        # Estructura final → estación + último registro
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

    def direccion_viento_texto(self, direccion_grados: float) -> str:
        """
        Convierte una dirección de viento en grados a su abreviatura (N, NE, E, SE, S, SO, O, NO).
        """
        if direccion_grados is None:
            return "N/A"
        
        direcciones = ["N", "NE", "E", "SE", "S", "SO", "O", "NO"]
        indice = round(direccion_grados / 45) % 8
        return direcciones[indice]


    def get_daily_summary(self, sensor_id: str, days: int = 30):
        desde = datetime.now() - timedelta(days=days)
        records = (
            self.db.query(
                SensorData.fecha,
                SensorData.temperatura,
                SensorData.humedad,
                SensorData.lluvia
            )
            .filter(SensorData.sensor_id == sensor_id)
            .filter(SensorData.fecha >= desde)
            .all()
        )
        if not records:
            return []

        resumen = {}
        for r in records:
            dia = r.fecha.date()
            if dia not in resumen:
                resumen[dia] = {
                    "total_lluvia": 0,
                    "temp_min": r.temperatura,
                    "temp_max": r.temperatura,
                    "humedad_max": r.humedad
                }
            resumen[dia]["total_lluvia"] += r.lluvia
            resumen[dia]["temp_min"] = min(resumen[dia]["temp_min"], r.temperatura)
            resumen[dia]["temp_max"] = max(resumen[dia]["temp_max"], r.temperatura)
            resumen[dia]["humedad_max"] = max(resumen[dia]["humedad_max"], r.humedad)

        # Convertimos a lista y dividimos lluvia por kmilimetro
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
    
    def get_monthly_daily_rain(self, sensor_id: str, year: int, month: int):
        """
        Entrada: sensor_id, año, mes
        Salida: lista de dicts con 'fecha' y 'suma_lluvia' para cada día del mes
        """
        # Consulta agregando SUM(lluvia) y filtrando por año/mes
        results = (
            self.db.query(
                func.date(SensorData.fecha).label("dia"),
                func.sum(SensorData.lluvia).label("suma_lluvia")
            )
            .filter(SensorData.sensor_id == sensor_id)
            .filter(extract("year", SensorData.fecha) == year)
            .filter(extract("month", SensorData.fecha) == month)
            .group_by(func.date(SensorData.fecha))
            .having(func.sum(SensorData.lluvia) > 0)
            .order_by(func.date(SensorData.fecha))
            .all()
        )

        # Convertimos a lista de dicts y dividimos por kmilimetro si quieres
        return [
            {"fecha": r.dia.isoformat(), "suma_lluvia": float(r.suma_lluvia)/self.kmilimetro}
            for r in results
        ]

    def get_year_daily_rain(self, sensor_id: str, year: int):
        """
        Entrada: sensor_id, año
        Salida: lista de dicts con 'fecha' y 'suma_lluvia' para cada día del mes
        """
        # Consulta agregando SUM(lluvia) y filtrando por año/mes
        results = (
            self.db.query(
                func.date(SensorData.fecha).label("dia"),
                func.sum(SensorData.lluvia).label("suma_lluvia")
            )
            .filter(SensorData.sensor_id == sensor_id)
            .filter(extract("year", SensorData.fecha) == year)
            .group_by(func.date(SensorData.fecha))
            .having(func.sum(SensorData.lluvia) > 0)
            .order_by(func.date(SensorData.fecha))
            .all()
        )

        # Convertimos a lista de dicts y dividimos por kmilimetro si quieres
        return [
            {"fecha": r.dia.isoformat(), "suma_lluvia": float(r.suma_lluvia)/self.kmilimetro}
            for r in results
        ]

    def get_rain_sum_between_dates(self, sensor_id: str, start_date: datetime, end_date: datetime):
        """
        Calcula la lluvia acumulada entre dos fechas (inclusive), usando solo la fecha (sin hora).
        
        :param sensor_id: ID de la estación/sensor
        :param start_date: fecha de inicio (datetime)
        :param end_date: fecha final (datetime)
        :return: suma de lluvia en kmilímetros
        """
        suma_lluvia = (
            self.db.query(func.sum(SensorData.lluvia))
            .filter(SensorData.sensor_id == sensor_id)
            .filter(cast(SensorData.fecha, Date) >= start_date.date())
            .filter(cast(SensorData.fecha, Date) <= end_date.date())
            .scalar()
        )
        
        return (suma_lluvia or 0.0) / self.kmilimetro
