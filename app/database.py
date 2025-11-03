from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker, declarative_base
from .config import settings

# URL desde el .env
SQLALCHEMY_DATABASE_URL = settings.DATABASE_URL

# Motor de base de datos
engine = create_engine(SQLALCHEMY_DATABASE_URL)

# Sesión de SQLAlchemy
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

# Base de los modelos
Base = declarative_base()

# Dependencia para inyección en FastAPI
def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
