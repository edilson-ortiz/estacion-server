import sys
import os
from logging.config import fileConfig
from sqlalchemy import engine_from_config, pool
from alembic import context

# Permite importar app
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from app.config import settings
from app.database import Base
from app.models import user,Estacion  # importa tus modelos

# Configuración de logging
config = context.config
fileConfig(config.config_file_name)

# Metadata de SQLAlchemy
target_metadata = Base.metadata

# Función para ignorar tablas si quieres (opcional)
def include_object(object, name, type_, reflected, compare_to):
    ignore_tables = [
    ]  # ejemplo: ['estacion', 'datos_sensores']
    if type_ == "table" and name in ignore_tables:
        return False
    return True

def run_migrations_online():
    connectable = engine_from_config(
        config.get_section(config.config_ini_section),
        prefix="sqlalchemy.",
        poolclass=pool.NullPool,
        url=settings.DATABASE_URL  # <- aquí usamos tu config
    )

    with connectable.connect() as connection:
        context.configure(
            connection=connection,
            target_metadata=target_metadata,
            include_object=include_object,
            compare_type=True,
        )

        with context.begin_transaction():
            context.run_migrations()

run_migrations_online()