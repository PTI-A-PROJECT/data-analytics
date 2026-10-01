"""konten soal osn: tipe, deskripsi, kode, gambar, tahun

Bank soal OSN (soal_osn/) memuat isian singkat selain pilihan ganda, teks
konteks bersama, potongan kode, dan gambar.

Revision ID: 0012
Revises: 0011
Create Date: 2026-09-30 14:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '0012'
down_revision: Union[str, Sequence[str], None] = '0011'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    with op.batch_alter_table('soal', schema=None) as batch_op:
        batch_op.add_column(sa.Column('tipe', sa.Enum('pilihan_ganda', 'isian_singkat', name='tipesoal', native_enum=False), server_default='pilihan_ganda', nullable=False))
        batch_op.add_column(sa.Column('deskripsi', sa.String(), nullable=True))
        batch_op.add_column(sa.Column('kode', sa.String(), nullable=True))
        batch_op.add_column(sa.Column('gambar', sa.String(), nullable=True))
        batch_op.add_column(sa.Column('tahun', sa.Integer(), nullable=True))


def downgrade() -> None:
    """Downgrade schema."""
    with op.batch_alter_table('soal', schema=None) as batch_op:
        batch_op.drop_column('tahun')
        batch_op.drop_column('gambar')
        batch_op.drop_column('kode')
        batch_op.drop_column('deskripsi')
        batch_op.drop_column('tipe')
