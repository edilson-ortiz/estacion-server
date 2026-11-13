"""add calibracion_pluviometro

Revision ID: 58792b3c4f5d
Revises: ee1e6c6cbc88
Create Date: 2026-06-25 07:59:20.272861

Nota: esta migración se generó en el servidor y se agregó al repo después.
Se protege con has_table porque en algunas BD la tabla ya existía.
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '58792b3c4f5d'
down_revision: Union[str, Sequence[str], None] = 'ee1e6c6cbc88'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    if sa.inspect(op.get_bind()).has_table('calibracion_pluviometro'):
        return
    op.create_table('calibracion_pluviometro',
    sa.Column('id', sa.Integer(), nullable=False),
    sa.Column('estacion_codigo', sa.String(length=50), nullable=False),
    sa.Column('factor_k', sa.Float(), nullable=False),
    sa.Column('vigente_desde', sa.DateTime(timezone=True), nullable=False),
    sa.Column('motivo', sa.String(length=255), nullable=True),
    sa.Column('creado_por', sa.String(length=100), nullable=True),
    sa.Column('created_at', sa.DateTime(timezone=True), nullable=False),
    sa.ForeignKeyConstraint(['estacion_codigo'], ['estacion.codigo'], ),
    sa.PrimaryKeyConstraint('id')
    )
    op.create_index(op.f('ix_calibracion_pluviometro_estacion_codigo'), 'calibracion_pluviometro', ['estacion_codigo'], unique=False)
    op.create_index(op.f('ix_calibracion_pluviometro_id'), 'calibracion_pluviometro', ['id'], unique=False)


def downgrade() -> None:
    """Downgrade schema."""
    op.drop_index(op.f('ix_calibracion_pluviometro_id'), table_name='calibracion_pluviometro')
    op.drop_index(op.f('ix_calibracion_pluviometro_estacion_codigo'), table_name='calibracion_pluviometro')
    op.drop_table('calibracion_pluviometro')
