from fastapi import FastAPI
from app.database import Base, engine
from app.routers import weather_router,pronostico_router

app = FastAPI(title="Estación Meteorológica API")

# Crear tablas si no existen
Base.metadata.create_all(bind=engine)

# Incluir rutas HTTP
app.include_router(weather_router.router,prefix="/weather", tags=["Weather Data"])
app.include_router(pronostico_router.router, prefix="/pronostico", tags=["Weather Data"])

@app.get("/")
def home():
    return {"status": "API funcionando con PostgreSQL"}
