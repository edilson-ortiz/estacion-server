import os
import sys
from logging.config import fileConfig

from sqlalchemy import engine_from_config, pool

from alembic import context

# Permite importar el paquete app
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

import app.models  # noqa: E402,F401  (registra todos los modelos en Base.metadata)
from app.core.config import settings  # noqa: E402
from app.db.base import Base  # noqa: E402

config = context.config
fileConfig(config.config_file_name)

target_metadata = Base.metadata

# Tablas de la BD que Alembic debe ignorar (ej: tablas de otros servicios)
IGNORE_TABLES: set[str] = set()


def include_object(object, name, type_, reflected, compare_to):
    return not (type_ == "table" and name in IGNORE_TABLES)


def run_migrations_offline():
    context.configure(
        url=settings.DATABASE_URL,
        target_metadata=target_metadata,
        include_object=include_object,
        literal_binds=True,
        compare_type=True,
    )
    with context.begin_transaction():
        context.run_migrations()


def run_migrations_online():
    connectable = engine_from_config(
        config.get_section(config.config_ini_section),
        prefix="sqlalchemy.",
        poolclass=pool.NullPool,
        url=settings.DATABASE_URL,
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


if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()
