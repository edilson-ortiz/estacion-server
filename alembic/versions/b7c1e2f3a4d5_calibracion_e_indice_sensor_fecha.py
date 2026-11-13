"""índice compuesto (sensor_id, fecha) en datos_sensores

- Índice (sensor_id, fecha): todas las consultas de datos filtran por estación + rango
  de fechas. Cubre al índice simple de sensor_id, que se elimina.
- ix_datos_sensores_id duplicaba la clave primaria.

Los índices se crean/eliminan CONCURRENTLY para no bloquear los inserts de las estaciones.

Revision ID: b7c1e2f3a4d5
Revises: d04bc23e748e
Create Date: 2026-11-11
"""
from typing import Sequence, Union

from alembic import op

revision: str = "b7c1e2f3a4d5"
down_revision: Union[str, Sequence[str], None] = "d04bc23e748e"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    with op.get_context().autocommit_block():
        op.create_index(
            "ix_datos_sensores_sensor_id_fecha",
            "datos_sensores",
            ["sensor_id", "fecha"],
            postgresql_concurrently=True,
            if_not_exists=True,
        )
        op.drop_index(
            "ix_datos_sensores_sensor_id", table_name="datos_sensores",
            postgresql_concurrently=True, if_exists=True,
        )
        op.drop_index(
            "ix_datos_sensores_id", table_name="datos_sensores",
            postgresql_concurrently=True, if_exists=True,
        )


def downgrade() -> None:
    with op.get_context().autocommit_block():
        op.create_index(
            "ix_datos_sensores_id", "datos_sensores", ["id"],
            postgresql_concurrently=True, if_not_exists=True,
        )
        op.create_index(
            "ix_datos_sensores_sensor_id", "datos_sensores", ["sensor_id"],
            postgresql_concurrently=True, if_not_exists=True,
        )
        op.drop_index(
            "ix_datos_sensores_sensor_id_fecha", table_name="datos_sensores",
            postgresql_concurrently=True, if_exists=True,
        )
