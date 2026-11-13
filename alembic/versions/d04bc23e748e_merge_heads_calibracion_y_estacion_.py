"""merge heads calibracion y estacion_usuario

Revision ID: d04bc23e748e
Revises: 58792b3c4f5d, a5dbd1dd5bc9
Create Date: 2026-07-25 23:48:35.646237

"""
from typing import Sequence, Union


# revision identifiers, used by Alembic.
revision: str = 'd04bc23e748e'
down_revision: Union[str, Sequence[str], None] = ('58792b3c4f5d', 'a5dbd1dd5bc9')
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    pass


def downgrade() -> None:
    """Downgrade schema."""
    pass
