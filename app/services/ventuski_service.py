import httpx
from bs4 import BeautifulSoup
import json
import re
from datetime import datetime
from typing import Any, Dict, List


class VentuskyService:
    
    HORARIOS = ["02:00", "05:00", "08:00", "11:00", "14:00", "17:00", "20:00", "23:00"]

    def __init__(self, lat: float, lon: float):
        self.lat = lat
        self.lon = lon

    # -------------------------------------------------------
    # 1️⃣ Descargar HTML
    # -------------------------------------------------------
    async def fetch_html(self) -> str:
        url = f"https://www.ventusky.com/es/{self.lat:.3f};{self.lon:.3f}"
        headers = {
            "User-Agent": "Mozilla/5.0 Chrome/120 Safari/537.36"
        }
        async with httpx.AsyncClient(follow_redirects=True, timeout=25) as client:
            r = await client.get(url, headers=headers)
            r.raise_for_status()
            return r.text

    # -------------------------------------------------------
    # 2️⃣ Extraer nota de coordenadas, altitud y fecha
    # -------------------------------------------------------
    @staticmethod
    def extract_page_note(soup: BeautifulSoup) -> Dict[str, Any]:
        note = soup.find("p", class_="note p-0")
        if not note:
            return {}

        text = note.get_text(strip=True)
        pattern = r"([0-9]+°[0-9]+'[NS]) / ([0-9]+°[0-9]+'[EW]) / Altitud (\d+) m / (\d{2}:\d{2} \d{2}/\d{2}/\d{4})"
        match = re.search(pattern, text)
        if not match:
            return {}

        lat_str, lon_str, alt, dt_str = match.groups()

        def dms_to_decimal(dms: str) -> float:
            deg, min_dir = dms.split("°")
            minutes = int(min_dir[:-1].replace("'", ""))
            direction = min_dir[-1]
            decimal = int(deg) + minutes / 60
            if direction in "SW":
                decimal *= -1
            return decimal

        return {
            "lat": dms_to_decimal(lat_str),
            "lon": dms_to_decimal(lon_str),
            "altitud_m": int(alt),
            "fecha_hora": datetime.strptime(dt_str, "%H:%M %d/%m/%Y").isoformat()
        }

    # -------------------------------------------------------
    # 3️⃣ Extraer fechas del select de días
    # -------------------------------------------------------
    @staticmethod
    def extract_astro_dates(soup: BeautifulSoup) -> List[str]:
        select = soup.find("select", id="date_selector")
        if not select:
            return []
        return [opt.get_text(strip=True) for opt in select.find_all("option")]

    # -------------------------------------------------------
    # 4️⃣ Parsear bloque JSON de pronóstico
    # -------------------------------------------------------
    @staticmethod
    def parse_forecast_html(html: str) -> Dict[str, Any]:
        soup = BeautifulSoup(html, "html.parser")
        custom = soup.find("custom-forecast")

        if not custom or not custom.has_attr("data-forecast"):
            return {"error": "No se encontró el pronóstico."}

        forecast = json.loads(custom["data-forecast"])
        note = VentuskyService.extract_page_note(soup)
        dates = VentuskyService.extract_astro_dates(soup)

        return {
            "forecast": forecast,
            "note": note,
            "astro_dates": dates
        }

    # -------------------------------------------------------
    # 5️⃣ Función principal: organiza por día/hora
    # -------------------------------------------------------
    async def get_forecast(self) -> Dict[str, Any]:
        html = await self.fetch_html()
        parsed = self.parse_forecast_html(html)

        if "error" in parsed:
            return parsed

        forecast = parsed["forecast"]
        note = parsed["note"]
        dates = parsed["astro_dates"]

        organized_days = []

        for idx, key in enumerate(sorted(forecast.keys())):
            if not key.startswith("d_"):
                continue

            day = forecast[key]
            day_info = {
                "id": key,
                "fecha": dates[idx] if idx < len(dates) else None,
                "horarios": []
            }

            for i, hora in enumerate(self.HORARIOS):
                hora_info = {
                    "hora": hora,
                    "temperatura": day.get("td", [None])[i] if "td" in day else None,
                    "precipitacion_mm": day.get("sr", [None])[i] if "sr" in day else None,
                    "probabilidad_precipitacion": day.get("rp", [None])[i] if "rp" in day else None,
                    "viento_direccion": day.get("vdId", [None])[i] if "vdId" in day else None,
                    "viento_velocidad": day.get("vsd", [None])[i] if "vsd" in day else None,
                    "descripcion": day.get("desc", [None])[i] if "desc" in day else None,
                }
                day_info["horarios"].append(hora_info)

            organized_days.append(day_info)

        return {
            "ubicacion": {
                "lat": note.get("lat", self.lat),
                "lon": note.get("lon", self.lon),
                "altitud_m": note.get("altitud_m")
            },
            "fecha_hora_nota": note.get("fecha_hora"),
            "dias": organized_days,
            "unidades": forecast.get("units", {}),
            "total_dias": len(organized_days),
            "astro_dates": dates
        }
