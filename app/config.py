from pydantic_settings import BaseSettings

class Settings(BaseSettings):
    DB_USER: str
    DB_PASSWORD: str
    DB_HOST: str
    DB_PORT: int
    DB_NAME: str
    CORREO: str
    API_KEY_TOMORROW: str

    class Config:
        env_file = "app/.env"

    @property
    def DATABASE_URL(self) -> str:
        """Construye la URL de conexión a PostgreSQL dinámicamente."""
        return (
            f"postgresql://{self.DB_USER}:{self.DB_PASSWORD}"
            f"@{self.DB_HOST}:{self.DB_PORT}/{self.DB_NAME}"
        )

settings = Settings()
