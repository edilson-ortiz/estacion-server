from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession
from sqlalchemy.orm import sessionmaker, DeclarativeBase
from app.config import settings

# ==============================
# Engine ASYNC
# ==============================

engine = create_async_engine(
    settings.DATABASE_URL,  # debe usar postgresql+asyncpg://
    echo=False,
    pool_pre_ping=True,
)

# ==============================
# Session Factory ASYNC
# ==============================

AsyncSessionLocal = sessionmaker(
    bind=engine,
    class_=AsyncSession,
    expire_on_commit=False,
)

# ==============================
# Base Declarativa (SQLAlchemy 2.0)
# ==============================

class Base(DeclarativeBase):
    pass

# ==============================
# Dependency for FastAPI
# ==============================

async def get_db():
    async with AsyncSessionLocal() as session:
        yield session