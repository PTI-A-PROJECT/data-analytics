"""soal.aktif: soal yang hilang dari bank sumber dinonaktifkan, bukan dihapus

Revision ID: 0013
Revises: 0012
Create Date: 2026-09-30 18:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '0013'
down_revision: Union[str, Sequence[str], None] = '0012'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    with op.batch_alter_table('soal', schema=None) as batch_op:
        batch_op.add_column(sa.Column('aktif', sa.Boolean(), server_default=sa.text('true'), nullable=False))


def downgrade() -> None:
    """Downgrade schema."""
    with op.batch_alter_table('soal', schema=None) as batch_op:
        batch_op.drop_column('aktif')
