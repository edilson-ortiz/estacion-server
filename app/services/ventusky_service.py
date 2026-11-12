"""Pronóstico obtenido por scraping de ventusky.com (usado por /pronostico/v1/ventusky)."""
import json
import re
from collections import Counter
from datetime import datetime
from typing import Any, Dict, List

from bs4 import BeautifulSoup

from app.core.config import settings
from app.core.http import TTLCache, get_http_client

_HEADERS = {"User-Agent": "Mozilla/5.0 Chrome/120 Safari/537.36"}
_NOTE_PATTERN = re.compile(
    r"([0-9]+°[0-9]+'[NS]) / ([0-9]+°[0-9]+'[EW]) / Altitud (\d+) m / (\d{2}:\d{2} \d{2}/\d{2}/\d{4})"
)
# Variables por horario y su valor por defecto si Ventusky no las trae
_VARIABLES = {"td": None, "sr": 0, "rp": None, "vdId": None, "vd45": None, "vsd": None, "vg": None}

_cache = TTLCache(settings.FORECAST_CACHE_TTL_SECONDS)


def _moda(valores: list) -> Any:
    return Counter(valores).most_common(1)[0][0] if valores else None


def _resumir(horas: list[dict]) -> dict:
    """Agrega un conjunto de horarios: suma de lluvia, min/max temp, viento promedio/máx, dirección más frecuente."""
    def presentes(clave: str) -> list:
        return [h[clave] for h in horas if h[clave] is not None]

    temperaturas = presentes("td")
    velocidades = presentes("vsd")
    rafagas = presentes("vg")
    return {
        "sr": sum(h["sr"] or 0 for h in horas),
        "td_min": min(temperaturas) if temperaturas else None,
        "td_max": max(temperaturas) if temperaturas else None,
        "vsd": sum(velocidades) / len(velocidades) if velocidades else None,
        "vg": max(rafagas) if rafagas else None,
        "vdId": _moda(presentes("vdId")),
        "vd45": _moda(presentes("vd45")),
    }


class VentuskyService:
    HORARIOS = ["02:00", "05:00", "08:00", "11:00", "14:00", "17:00", "20:00", "23:00"]
    TRAMOS = {
        "madrugada": ["02:00", "05:00"],
        "mañana": ["08:00", "11:00"],
        "tarde": ["14:00", "17:00"],
        "noche": ["20:00", "23:00"],
    }

    def __init__(self, lat: float, lon: float):
        self.lat = lat
        self.lon = lon
        self.raw_forecast: dict | None = None
        self.note: dict | None = None
        self.astro_dates: list | None = None
        self.organized_days: list | None = None

    # -----------------------------
    # Descarga y parseo
    # -----------------------------
    async def fetch_html(self) -> str:
        url = f"https://www.ventusky.com/es/{self.lat:.3f};{self.lon:.3f}"
        r = await get_http_client().get(url, headers=_HEADERS, follow_redirects=True, timeout=25)
        r.raise_for_status()
        return r.text

    @staticmethod
    def extract_page_note(soup: BeautifulSoup) -> Dict[str, Any]:
        note = soup.find("p", class_="note p-0")
        if not note:
            return {}
        match = _NOTE_PATTERN.search(note.get_text(strip=True))
        if not match:
            return {}

        lat_str, lon_str, alt, dt_str = match.groups()

        def dms_to_decimal(dms: str) -> float:
            deg, min_dir = dms.split("°")
            minutes = int(min_dir[:-1].replace("'", ""))
            decimal = int(deg) + minutes / 60
            return -decimal if min_dir[-1] in "SW" else decimal

        return {
            "lat": dms_to_decimal(lat_str),
            "lon": dms_to_decimal(lon_str),
            "altitud_m": int(alt),
            "fecha_hora": datetime.strptime(dt_str, "%H:%M %d/%m/%Y").isoformat(),
        }

    @staticmethod
    def extract_astro_dates(soup: BeautifulSoup) -> List[str]:
        select = soup.find("select", id="date_selector")
        if not select:
            return []
        return [opt.get_text(strip=True) for opt in select.find_all("option")]

    @staticmethod
    def parse_forecast_html(html: str) -> Dict[str, Any]:
        soup = BeautifulSoup(html, "html.parser")
        custom = soup.find("custom-forecast")
        if not custom or not custom.has_attr("data-forecast"):
            return {"error": "No se encontró el pronóstico."}
        return {
            "forecast": json.loads(custom["data-forecast"]),
            "note": VentuskyService.extract_page_note(soup),
            "astro_dates": VentuskyService.extract_astro_dates(soup),
        }

    async def _download_and_parse(self) -> Dict[str, Any]:
        parsed = self.parse_forecast_html(await self.fetch_html())
        if "error" in parsed:
            raise Exception(parsed["error"])
        return parsed

    async def load_forecast(self) -> None:
        """Descarga (o toma de caché) y organiza el pronóstico. Llamar una vez antes de los get_*."""
        parsed = await _cache.get_or_set((self.lat, self.lon), self._download_and_parse)

        self.raw_forecast = parsed["forecast"]
        self.note = parsed["note"]
        self.astro_dates = parsed["astro_dates"]

        self.organized_days = []
        for idx, key in enumerate(sorted(self.raw_forecast.keys())):
            if not key.startswith("d_"):
                continue
            day = self.raw_forecast[key]
            self.organized_days.append({
                "id": key,
                "fecha": self.astro_dates[idx] if idx < len(self.astro_dates) else None,
                "horarios": [
                    {"h": hora, **{k: (day[k][i] if k in day else default) for k, default in _VARIABLES.items()}}
                    for i, hora in enumerate(self.HORARIOS)
                ],
            })

    # -----------------------------
    # Vistas del pronóstico
    # -----------------------------
    def get_forecast_hourly(self) -> List[Dict[str, Any]]:
        return self.organized_days

    def get_forecast_daily(self) -> List[Dict[str, Any]]:
        return [
            {"fecha": dia["fecha"], **_resumir(dia["horarios"])}
            for dia in self.organized_days
            if dia["horarios"]
        ]

    def get_forecast_by_tramos(self) -> List[Dict[str, Any]]:
        resumen = []
        for dia in self.organized_days:
            resumen_dia = {"fecha": dia["fecha"]}
            for tramo, horas_tramo in self.TRAMOS.items():
                horas = [h for h in dia["horarios"] if h["h"] in horas_tramo]
                if horas:
                    resumen_dia[tramo] = _resumir(horas)
            resumen.append(resumen_dia)
        return resumen
