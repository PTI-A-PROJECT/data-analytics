"""dokumen Materi: materi.topik & halaman_materi.judul (ingest dari Materi/*.docx)

Revision ID: 0014
Revises: 0013
Create Date: 2026-09-30 20:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '0014'
down_revision: Union[str, Sequence[str], None] = '0013'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    with op.batch_alter_table('materi', schema=None) as batch_op:
        batch_op.add_column(sa.Column('topik', sa.Integer(), nullable=True))
    with op.batch_alter_table('halaman_materi', schema=None) as batch_op:
        batch_op.add_column(sa.Column('judul', sa.String(), nullable=True))


def downgrade() -> None:
    """Downgrade schema."""
    with op.batch_alter_table('halaman_materi', schema=None) as batch_op:
        batch_op.drop_column('judul')
    with op.batch_alter_table('materi', schema=None) as batch_op:
        batch_op.drop_column('topik')
