# Estación Meteorológica API

Backend FastAPI de las estaciones meteorológicas IAgro. Lo consume la app móvil (Flutter)
y servirá también al futuro panel administrativo.

> ⚠️ **Contrato con la app móvil**: las rutas, parámetros y formatos de respuesta existentes
> no deben cambiar. Las funcionalidades nuevas van en rutas nuevas (por ejemplo `/admin/...`).

## Estructura

```
app/
├── main.py              # Crea la app: lifespan, CORS, manejador de errores, routers
├── api/
│   ├── router.py        # Registro central de routers (aquí se agrega el router admin)
│   ├── deps.py          # Dependencias: get_current_user, require_admin
│   └── routers/         # Endpoints HTTP (solo reciben/validan y delegan a services)
│       ├── auth.py          /auth/*
│       ├── estacion.py      /api/stations/*
│       ├── weather.py       /weather/*
│       └── pronostico.py    /pronostico/*
├── core/
│   ├── config.py        # Settings (.env)
│   ├── security.py      # Hash de contraseñas y JWT
│   ├── exceptions.py    # Formato estándar de error {success, message, data}
│   ├── http.py          # Cliente HTTP compartido + caché TTL
│   └── time.py          # Zona horaria Bolivia, "estación activa", etc.
├── db/
│   ├── base.py          # Base declarativa
│   └── session.py       # Engine async, AsyncSessionLocal, get_db
├── models/              # Modelos SQLAlchemy (users, estacion, datos_sensores, ...)
├── schemas/             # Modelos Pydantic de entrada/salida
└── services/            # Lógica de negocio
    ├── auth_service.py
    ├── station_service.py
    ├── weather_service.py     # Consultas y agregados de datos de sensores
    ├── calibracion.py         # Factor del pluviómetro (pulsos → mm), en SQL y en memoria
    ├── forecast_service.py    # Pronóstico iagro360 (con caché)
    └── ventusky_service.py    # Pronóstico Ventusky por scraping (con caché)
alembic/                 # Migraciones de BD
scripts/                 # Scripts de mantenimiento (seed de calibraciones, ...)
```

**Regla de capas:** `routers → services → models`. Los routers no hacen consultas;
los services no conocen detalles HTTP salvo `HTTPException` para errores de negocio.

## Puesta en marcha

```bash
python -m venv .venv
.venv\Scripts\activate          # Windows  (Linux/macOS: source .venv/bin/activate)
pip install -r requirements.txt
cp .env.example .env            # y completar los valores
alembic upgrade head
python run.py                   # desarrollo (Windows o Linux), con autorecarga
```

En producción (Linux): `uvicorn app.main:app --host 0.0.0.0 --port 8000`.
En Windows, `uvicorn` sin `--reload` falla con psycopg async (ProactorEventLoop);
`run.py` lo resuelve. Para probar desde el celular en la misma red: `HOST=0.0.0.0 python run.py`.

Documentación interactiva: http://localhost:8000/docs

## Migraciones

```bash
alembic revision --autogenerate -m "descripcion"   # tras cambiar un modelo
alembic upgrade head
```

## Calibración del pluviómetro

La lluvia se guarda en **pulsos crudos** en `datos_sensores.lluvia`. Cada estación tiene en
`calibracion_pluviometro` uno o varios factores con fecha de vigencia; a cada lectura se le
aplica el factor vigente en su fecha (0.1 por defecto). Toda la lógica está en
`app/services/calibracion.py`.

Cargar los factores iniciales: `python -m scripts.seed_calibracion`

## Agregar el panel administrativo (guía)

1. Crear `app/api/routers/admin.py` con `router = APIRouter(dependencies=[Depends(require_admin)])`.
2. Registrarlo en `app/api/router.py` con `prefix="/admin"`.
3. Lógica en `app/services/` (reutilizar `StationService`, `WeatherService`).
4. Definir `CORS_ORIGINS` en `.env` con el dominio del panel.
