"""Inserta el factor de calibración inicial del pluviómetro para una lista de estaciones.

Uso (desde la raíz del proyecto):
    python -m scripts.seed_calibracion
"""
import asyncio
import selectors
import sys
from datetime import datetime, timezone

from app.db.session import AsyncSessionLocal, engine
from app.models import CalibracionPluviometro

# Códigos EXACTOS como están en la tabla estacion
EQUIPOS = [
    {"codigo": "EP057", "factor_k": 0.1},
    {"codigo": "EP999", "factor_k": 0.1},
    {"codigo": "EP003", "factor_k": 0.1},
    {"codigo": "EP001", "factor_k": 0.1},
    {"codigo": "EP002", "factor_k": 0.1},
    {"codigo": "TEST", "factor_k": 0.1},
    {"codigo": "EP055", "factor_k": 0.1},
    {"codigo": "EP056", "factor_k": 0.1},
    {"codigo": "EP058", "factor_k": 0.1},
    {"codigo": "EP059", "factor_k": 0.1},
    {"codigo": "EP060", "factor_k": 0.1},
    {"codigo": "EP061", "factor_k": 0.1},
    {"codigo": "EP062", "factor_k": 0.1},
    {"codigo": "EP063", "factor_k": 0.1},
    {"codigo": "EP064", "factor_k": 0.1},
]


async def seed():
    async with AsyncSessionLocal() as db:
        for e in EQUIPOS:
            db.add(CalibracionPluviometro(
                estacion_codigo=e["codigo"],
                factor_k=e["factor_k"],
                vigente_desde=datetime(2000, 1, 1, tzinfo=timezone.utc),
                motivo="factor inicial",
            ))
        await db.commit()
    await engine.dispose()
    print("✅ Calibraciones insertadas correctamente")


if __name__ == "__main__":
    if sys.platform == "win32":
        # psycopg async no es compatible con el ProactorEventLoop de Windows
        asyncio.run(seed(), loop_factory=lambda: asyncio.SelectorEventLoop(selectors.SelectSelector()))
    else:
        asyncio.run(seed())
