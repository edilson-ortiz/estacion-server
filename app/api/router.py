"""Registro central de routers. Para el panel administrativo, agregar aquí p. ej.:

    api_router.include_router(admin.router, prefix="/admin", tags=["Admin"])
"""
from fastapi import APIRouter

from app.api.routers import auth, estacion, pronostico, weather, webhooks

api_router = APIRouter()

# ⚠️ Prefijos y rutas usados por la app móvil: no modificar.
api_router.include_router(auth.router)
api_router.include_router(estacion.router)
api_router.include_router(weather.router, prefix="/weather", tags=["Weather Data"])
api_router.include_router(pronostico.router, prefix="/pronostico", tags=["Pronóstico"])

# Ingesta de datos (EMQX → API → BD)
api_router.include_router(webhooks.router, prefix="/webhooks", tags=["Webhooks"])
