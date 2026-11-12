from contextlib import asynccontextmanager

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware

from app.api.router import api_router
from app.core.config import settings
from app.core.exceptions import http_exception_handler
from app.core.http import close_http_client
from app.db.session import engine


@asynccontextmanager
async def lifespan(app: FastAPI):
    yield
    # Cierre ordenado de conexiones al apagar
    await close_http_client()
    await engine.dispose()


app = FastAPI(title=settings.APP_NAME, lifespan=lifespan)

if settings.cors_origins:
    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.cors_origins,
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

app.add_exception_handler(HTTPException, http_exception_handler)
app.include_router(api_router)


@app.get("/")
def home():
    return {"status": "API funcionando con PostgreSQL"}
