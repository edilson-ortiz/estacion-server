from functools import cached_property

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    APP_NAME: str = "Estación Meteorológica API"

    # ---------------- Base de datos ----------------
    DB_USER: str
    DB_PASSWORD: str
    DB_HOST: str
    DB_PORT: int
    DB_NAME: str
    DB_POOL_SIZE: int = 10
    DB_MAX_OVERFLOW: int = 20
    DB_ECHO: bool = False

    # ---------------- Seguridad / JWT ----------------
    SECRET_KEY: str
    ALGORITHM: str = "HS256"
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 30
    REFRESH_TOKEN_EXPIRE_DAYS: int = 7

    # ---------------- CORS (para el futuro panel web) ----------------
    # Lista separada por comas, ej: "https://panel.iagro.bo,http://localhost:5173"
    # Vacío = sin CORS (la app móvil no lo necesita).
    CORS_ORIGINS: str = ""

    # ---------------- Webhook de EMQX (ingesta de datos de estaciones) ----------------
    # EMQX debe enviar este valor en el header X-Webhook-Token. Vacío = webhook desactivado.
    EMQX_WEBHOOK_TOKEN: str = ""

    # ---------------- Servicios externos ----------------
    HTTP_TIMEOUT_SECONDS: float = 30.0
    FORECAST_URL: str = "https://pronostico.iagro360.xyz/forecast/daytramo"
    FORECAST_CACHE_TTL_SECONDS: int = 600  # 0 = sin caché

    @property
    def DATABASE_URL(self) -> str:
        """URL de PostgreSQL con psycopg 3 (sirve tanto sync como async)."""
        return (
            f"postgresql+psycopg://{self.DB_USER}:{self.DB_PASSWORD}"
            f"@{self.DB_HOST}:{self.DB_PORT}/{self.DB_NAME}"
        )

    @cached_property
    def cors_origins(self) -> list[str]:
        return [o.strip() for o in self.CORS_ORIGINS.split(",") if o.strip()]


settings = Settings()
