# seed_calibracion.py
import asyncio
import selectors
from datetime import datetime, timezone
from app.database import AsyncSessionLocal
from app.models.Estacion import CalibracionPluviometro
# ← Pon aquí los codigos EXACTOS como están en tu tabla estacion
equipos = [
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
    {"codigo": "EP064", "factor_k": 0.1}
]

async def seed():
    async with AsyncSessionLocal() as db:
        for e in equipos:
            db.add(CalibracionPluviometro(
                estacion_codigo=e["codigo"],
                factor_k=e["factor_k"],
                vigente_desde=datetime(2000, 1, 1, tzinfo=timezone.utc),
                motivo="factor inicial"
            ))
        await db.commit()
        print("✅ Calibraciones insertadas correctamente")

# ← Fix para Windows (ProactorEventLoop no compatible con psycopg async)
asyncio.run(seed(), loop_factory=lambda: asyncio.SelectorEventLoop(selectors.SelectSelector()))