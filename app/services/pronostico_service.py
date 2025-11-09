from fastapi import APIRouter, HTTPException
from app.config import settings
import httpx
from collections import defaultdict
from datetime import datetime
import locale

class PronosticoService:
    async def get_met_no(self, lat:float, lon:float):
        #lat, lon, altitude = -17.856667, -63.036667, 416  # luego lo obtendrás desde la BD
        coord = {
            "lat": lat,
            "lon": lon
        }

        response = {}
        response["coord"] = coord
        response['dias'] = await self.promedio_diario(lat, lon)
        response['periodos'] = await self.promedio_por_periodo(lat, lon)

        return response

        

    async def promedio_diario(self, lat: float, lon: float):
        # Configurar locale para obtener los días en español
        try:
            locale.setlocale(locale.LC_TIME, "es_ES.utf8")
        except:
            # En Windows puede ser distinto
            locale.setlocale(locale.LC_TIME, "es_ES")

        pro1 = await self.process_met_data(lat, lon)
        pro2 = await self.process_tomorrow_data(lat, lon)

        datos1 = await self.agrupar_por_dia(pro1)
        datos2 = await self.agrupar_por_dia(pro2)

        promedio_diario = []
        fechas = {item["fecha"] for item in datos1} | {item["fecha"] for item in datos2}

        for fecha in sorted(fechas):
            d1 = next((x for x in datos1 if x["fecha"] == fecha), None)
            d2 = next((x for x in datos2 if x["fecha"] == fecha), None)

            if not d1 and not d2:
                continue

            def avg(key):
                v1 = d1.get(key) if d1 else None
                v2 = d2.get(key) if d2 else None
                valores = [v for v in [v1, v2] if v is not None]
                if not valores:
                    return None
                return sum(valores) / len(valores)

            # Obtener nombre del día (abreviado, ej: "lun", "mar", "mié")
            fecha_dt = datetime.strptime(fecha, "%Y-%m-%d")
            dia_semana = fecha_dt.strftime("%A").capitalize()  # ej: "Lun"

            promedio_diario.append({
                "fecha": fecha,
                "dia": dia_semana,
                "temperatura_maxima_c": int(avg("temperatura_maxima_c")),
                "temperatura_minima_c": int(avg("temperatura_minima_c")),
                "humedad_relativa_%": int(avg("humedad_relativa_%")),
                "precipitacion_total_mm": int(avg("precipitacion_total_mm")),
            })

        return promedio_diario

    async def promedio_por_periodo(self, lat: float, lon: float):
        """
        Calcula el promedio por periodos y organiza los datos por fecha y
        por periodo: madrugada, mañana, tarde, noche.
        """

        # Configurar locale en español
        try:
            locale.setlocale(locale.LC_TIME, "es_ES.utf8")
        except:
            locale.setlocale(locale.LC_TIME, "es_ES")

        # Obtener datos procesados de ambas fuentes
        datos_met = await self.process_met_data(lat, lon)
        datos_tomorrow = await self.process_tomorrow_data(lat, lon)

        # Agrupar por periodo
        periodos_met = await self.agrupar_por_periodo(datos_met)
        periodos_tomorrow = await self.agrupar_por_periodo(datos_tomorrow)

        # Crear diccionario por fecha y por periodo
        datos_por_fecha = {}

        # Obtener todas las claves "fecha_periodo"
        claves = {item["fecha_periodo"] for item in periodos_met} | {item["fecha_periodo"] for item in periodos_tomorrow}

        for clave in sorted(claves):
            d1 = next((x for x in periodos_met if x["fecha_periodo"] == clave), None)
            d2 = next((x for x in periodos_tomorrow if x["fecha_periodo"] == clave), None)

            fecha, periodo = clave.split("_")
            fecha_dt = datetime.strptime(fecha, "%Y-%m-%d")
            dia_semana = fecha_dt.strftime("%A").capitalize()

            def formatear_datos(d):
                if not d:
                    return None
                return {
                    "temperatura_maxima_c": int(d.get("temperatura_maxima_c", 0)),
                    "temperatura_minima_c": int(d.get("temperatura_minima_c", 0)),
                    "humedad_relativa_%": int(d.get("humedad_relativa_%", 0)),
                    "viento_velocidad_k_h": int(d.get("viento_velocidad_k_h", 0)),
                    "viento_direccion_grados": int(d.get("viento_direccion_grados")),
                    "precipitacion_total_mm": int(d.get("precipitacion_total_mm", 0)),
                }

            def avg(key):
                v1 = d1.get(key) if d1 else None
                v2 = d2.get(key) if d2 else None
                valores = [v for v in [v1, v2] if v is not None]
                return round(sum(valores) / len(valores), 2) if valores else None

            # Inicializar la fecha si no existe
            if fecha not in datos_por_fecha:
                datos_por_fecha[fecha] = {
                    "dia": dia_semana,
                    "periodos": {}
                }

            # Agregar los datos por periodo en orden
            datos_por_fecha[fecha]["periodos"][periodo] = {
                "Met.no": formatear_datos(d1) if d1 else None,
                "Tomorrow.io": formatear_datos(d2) if d2 else None,
                "Promedio": {
                    "temperatura_maxima_c": int(avg("temperatura_maxima_c")),
                    "temperatura_minima_c": int(avg("temperatura_minima_c")),
                    "humedad_relativa_%": int(avg("humedad_relativa_%")),
                    "viento_velocidad_k_h": int(avg("viento_velocidad_k_h")),
                    "viento_direccion_grados": int(avg("viento_direccion_grados")),
                    "precipitacion_total_mm": int(avg("precipitacion_total_mm")),
                }
            }

        # Convertir a lista ordenada por fecha y periodos
        resultado_final = []
        orden_periodos = ["madrugada", "mañana", "tarde", "noche"]
        for fecha in sorted(datos_por_fecha):
            dia_info = datos_por_fecha[fecha]["dia"]
            periodos_info = datos_por_fecha[fecha]["periodos"]
            for periodo in orden_periodos:
                if periodo in periodos_info:
                    resultado_final.append({
                        "fecha": fecha,
                        "dia": dia_info,
                        "periodo": periodo,
                        **periodos_info[periodo]
                    })

        return resultado_final




    async def agrupar_por_dia(self, datos_horarios):
        """
        Agrupa los datos horarios por día completo.

        Calcula:
        - Promedio: temperatura, humedad, viento velocidad, dirección viento
        - Suma: precipitaciones
        """

        agrupado_dia = defaultdict(list)

        # Agrupar por día
        for item in datos_horarios:
            fecha = item['time'][:10]
            agrupado_dia[fecha].append(item)

        resumen = []
        for fecha, items in agrupado_dia.items():
            temp_max = max((i.get('temperatura_maxima_c') or i.get('temperatura_c') or 0) for i in items)
            temp_min = min((i.get('temperatura_minima_c') or i.get('temperatura_c') or 0) for i in items)
            humedad = sum((i.get('humedad_relativa_%') or 0) for i in items) / len(items)
            viento_vel = sum((i.get('viento_velocidad_k_h') or 0) for i in items) / len(items)
            viento_dir = sum((i.get('viento_direccion_grados') or 0) for i in items) / len(items)
            precipitacion = sum((i.get('precipitacion') or 0) for i in items)

            resumen.append({
                "fecha": fecha,
                "temperatura_maxima_c": round(temp_max, 2),
                "temperatura_minima_c": round(temp_min, 2),
                "humedad_relativa_%": round(humedad, 2),
                "viento_velocidad_k_h": round(viento_vel, 2),
                "viento_direccion_grados": round(viento_dir, 2),
                "precipitacion_total_mm": round(precipitacion, 2),
            })

        return resumen

    async def agrupar_por_periodo(self,datos_horarios):
        """
        Agrupa datos horarios en bloques del día:
        - madrugada: 0-5
        - mañana: 6-11
        - tarde: 12-17
        - noche: 18-23

        Calcula:
        - Promedio para temperatura, humedad y viento
        - Promedio para dirección de viento (simplemente promedio numérico)
        - Suma para precipitaciones
        """
        # Definimos los periodos
        periodos = {
            'madrugada': range(0, 6),
            'mañana': range(6, 12),
            'tarde': range(12, 18),
            'noche': range(18, 24)
        }

        agrupado = defaultdict(list)

        # Agrupar por día y periodo
        for item in datos_horarios:
            hora = int(item['time'][11:13])  # extraemos la hora del string ISO
            fecha = item['time'][:10]        # extraemos la fecha
            for periodo, horas in periodos.items():
                if hora in horas:
                    key = f"{fecha}_{periodo}"
                    agrupado[key].append(item)
                    break

        # Procesar cada grupo para calcular promedio y suma
        resumen = []
        for key, items in agrupado.items():

            temp_max = max((i.get('temperatura_maxima_c') or i.get('temperatura_c') or 0) for i in items)
            temp_min = min((i.get('temperatura_minima_c') or i.get('temperatura_c') or 0) for i in items)
            humedad = sum((i.get('humedad_relativa_%') or 0) for i in items) / len(items)
            viento_vel = sum((i.get('viento_velocidad_k_h') or 0) for i in items) / len(items)
            viento_dir = sum((i.get('viento_direccion_grados') or 0) for i in items) / len(items)
            precipitacion = sum((i.get('precipitacion') or 0) for i in items)


            resumen.append({
                "fecha_periodo": key,
                "temperatura_maxima_c": round(temp_max, 2),
                "temperatura_minima_c": round(temp_min, 2),
                "humedad_relativa_%": round(humedad, 2),
                "viento_velocidad_k_h": round(viento_vel, 2),
                "viento_direccion_grados": round(viento_dir, 2),
                "precipitacion_total_mm": round(precipitacion, 2),
            })

        return resumen

    async def process_tomorrow_data(self, lat: float, lon: float):
        data = await self.get_weatherapi_tomorrow(lat, lon)
        datos_procesados = []
         # Recorremos cada hora del timeline
        for pro in data.get('timelines', {}).get('hourly', []):
            valores = pro.get('values', {})

            item = {
                "time": pro.get('time'),
                "presion_barometrica_hpa": valores.get('pressureSeaLevel'),
                "temperatura_c": valores.get('temperature'),
                "humedad_relativa_%": valores.get('humidity'),
                "viento_velocidad_k_h": valores.get('windSpeed')*3.6,
                "viento_direccion_grados": valores.get('windDirection'),
                "precipitacion": valores.get('rainAccumulation'),
                # Puedes agregar más campos si los necesitas
            }

            datos_procesados.append(item)
        return datos_procesados

    async def get_weatherapi_tomorrow(self, lat: float, lon: float):
        
        url = f"https://api.tomorrow.io/v4/weather/forecast?location={lat},{lon}&timesteps=1h&apikey={settings.API_KEY_TOMORROW}"
        

        async with httpx.AsyncClient() as client:
            response = await client.get(url)

        if response.status_code != 200:
            raise HTTPException(status_code=response.status_code, detail="Error al obtener datos de tomorrow.io")

        return response.json()  # devuelve directamente lo que responde la API
    

    async def process_met_data(self, lat: float, lon: float, altitude: int=416):

        response = await self.get_weatherapi_met(lat, lon, altitude)

        datos_procesados = []
        for pro in response['properties']['timeseries']:
            tiempo = pro['time']
            instant = pro['data'].get('instant', {}).get('details', {})
            next_1h = pro['data'].get('next_1_hours', {}).get('details', {})
            next_6h = pro['data'].get('next_6_hours', {}).get('details', {})
            next_12h = pro['data'].get('next_12_hours', {}).get('details', {})
            # Crear el diccionario con los datos requeridos
            item = {
                "time": tiempo,       
                "presion_barometrica_hpa": instant.get('air_pressure_at_sea_level'),        
                "temperatura_minima_c": next_6h.get('air_temperature_min'),
                "temperatura_maxima_c": next_6h.get('air_temperature_max'),
                "humedad_relativa_%": instant.get('relative_humidity'),
                "viento_velocidad_k_h": instant.get('wind_speed')*3.6,
                "viento_direccion_grados": instant.get('wind_from_direction'),
                "precipitacion": next_6h.get('precipitation_amount'),
            }
            datos_procesados.append(item)
        return datos_procesados

    async def get_weatherapi_met(self,  lat: float, lon: float, altitude: int =416):

        url = f"https://api.met.no/weatherapi/locationforecast/2.0/complete?lat={lat}&lon={lon}&altitude={altitude}"
        headers = {
            f"User-Agent": "IAGRO-METEO/1.0 ({settings.CORREO})"  # obligatorio para Met.no
        }

        async with httpx.AsyncClient() as client:
            response = await client.get(url, headers=headers)

        if response.status_code != 200:
            raise HTTPException(status_code=response.status_code, detail="Error al obtener datos de Met.no")

        return response.json()  # devuelve directamente lo que responde la API
