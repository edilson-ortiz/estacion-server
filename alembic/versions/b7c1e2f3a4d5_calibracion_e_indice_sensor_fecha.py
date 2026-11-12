"""calibracion_pluviometro (si falta) + índice compuesto (sensor_id, fecha)

- La tabla calibracion_pluviometro existía en las BD actuales pero ninguna migración
  la creaba: en una instalación nueva `alembic upgrade head` la dejaba fuera.
- Índice (sensor_id, fecha): todas las consultas de datos filtran por estación + rango
  de fechas. Cubre al índice simple de sensor_id, que se elimina.
- ix_datos_sensores_id duplicaba la clave primaria.

Los índices se crean/eliminan CONCURRENTLY para no bloquear los inserts de las estaciones.

Revision ID: b7c1e2f3a4d5
Revises: a5dbd1dd5bc9
Create Date: 2026-11-11
"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "b7c1e2f3a4d5"
down_revision: Union[str, Sequence[str], None] = "a5dbd1dd5bc9"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    if not sa.inspect(op.get_bind()).has_table("calibracion_pluviometro"):
        op.create_table(
            "calibracion_pluviometro",
            sa.Column("id", sa.Integer(), nullable=False),
            sa.Column("estacion_codigo", sa.String(length=50), nullable=False),
            sa.Column("factor_k", sa.Float(), nullable=False),
            sa.Column("vigente_desde", sa.DateTime(timezone=True), nullable=False),
            sa.Column("motivo", sa.String(length=255), nullable=True),
            sa.Column("creado_por", sa.String(length=100), nullable=True),
            sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
            sa.ForeignKeyConstraint(["estacion_codigo"], ["estacion.codigo"]),
            sa.PrimaryKeyConstraint("id"),
        )
        op.create_index("ix_calibracion_pluviometro_id", "calibracion_pluviometro", ["id"])
        op.create_index(
            "ix_calibracion_pluviometro_estacion_codigo", "calibracion_pluviometro", ["estacion_codigo"]
        )

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
    # calibracion_pluviometro no se elimina: ya existía antes de esta migración en las BD actuales.
