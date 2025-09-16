from fastapi import FastAPI
#from app import models
from app.database import get_connection
from app.routers import sensors

app = FastAPI(title="Estación Meteorológica API")

# Crear tabla si no existe
conn = get_connection()
cursor = conn.cursor()
#cursor.execute(models.CREATE_TABLE_QUERY)
conn.commit()
cursor.close()
conn.close()

# Incluir rutas HTTP
app.include_router(sensors.router)

@app.get("/")
def home():
    return {"status": "API funcionando con MQTT y PostgreSQL"}
