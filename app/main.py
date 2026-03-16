from fastapi import FastAPI
from app.database import Base, engine
from app.routers import auth, weather_router,pronostico_router,estacion
from fastapi.exceptions import HTTPException
from app.core.exception_handler import http_exception_handler

app = FastAPI(title="Estación Meteorológica API")

app.add_exception_handler(HTTPException, http_exception_handler)

async def init_models():
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)

# Incluir rutas HTTP
app.include_router(auth.router)
app.include_router(estacion.router)
app.include_router(weather_router.router,prefix="/weather", tags=["Weather Data"])
app.include_router(pronostico_router.router, prefix="/pronostico", tags=["Weather Data"])


@app.get("/")
def home():
    return {"status": "API funcionando con PostgreSQL"}
