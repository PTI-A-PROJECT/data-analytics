"""leaderboard: snapshot nama & durasi di hasil_tes

Nama siswa & nama sekolah (dikirim fullstack saat submit) dan durasi
pengerjaan per attempt, untuk Leaderboard per Tingkat Seleksi.

Revision ID: 0011
Revises: 0010
Create Date: 2026-09-30 10:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '0011'
down_revision: Union[str, Sequence[str], None] = '0010'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    with op.batch_alter_table('hasil_tes', schema=None) as batch_op:
        batch_op.add_column(sa.Column('nama_siswa', sa.String(), nullable=True))
        batch_op.add_column(sa.Column('nama_sekolah', sa.String(), nullable=True))
        batch_op.add_column(sa.Column('durasi_detik', sa.Numeric(precision=10, scale=2, asdecimal=False), nullable=True))


def downgrade() -> None:
    """Downgrade schema."""
    with op.batch_alter_table('hasil_tes', schema=None) as batch_op:
        batch_op.drop_column('durasi_detik')
        batch_op.drop_column('nama_sekolah')
        batch_op.drop_column('nama_siswa')
