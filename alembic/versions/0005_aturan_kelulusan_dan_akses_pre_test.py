"""aturan kelulusan dan akses pre test tiket 15

Revision ID: 0005
Revises: 0004
Create Date: 2026-09-29 20:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '0005'
down_revision: Union[str, Sequence[str], None] = '0004'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    op.add_column(
        'akses_tingkat_siswa',
        sa.Column('simulasi_terbuka', sa.Boolean(), server_default=sa.text('0'), nullable=False),
    )

    op.create_table(
        'aturan_pre_test',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('tingkat_seleksi_id', sa.Integer(), nullable=False),
        sa.Column('skor_min', sa.Numeric(precision=5, scale=2, asdecimal=False), nullable=False),
        sa.Column('aktif', sa.Boolean(), server_default=sa.text('1'), nullable=False),
        sa.Column('dibuat_pada', sa.DateTime(timezone=True), server_default=sa.text('(CURRENT_TIMESTAMP)'), nullable=False),
        sa.Column('diperbarui_pada', sa.DateTime(timezone=True), server_default=sa.text('(CURRENT_TIMESTAMP)'), nullable=False),
        sa.CheckConstraint('skor_min >= 0 AND skor_min <= 100', name=op.f('ck_aturan_pre_test_ck_aturan_pre_test_skor_rentang')),
        sa.ForeignKeyConstraint(['tingkat_seleksi_id'], ['tingkat_seleksi.id'], name=op.f('fk_aturan_pre_test_tingkat_seleksi_id_tingkat_seleksi'), ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('id', name=op.f('pk_aturan_pre_test')),
        sa.UniqueConstraint('tingkat_seleksi_id', name=op.f('uq_aturan_pre_test_tingkat_seleksi_id'))
    )

    op.create_table(
        'riwayat_evaluasi_pre_test',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('siswa_id', sa.String(), nullable=False),
        sa.Column('hasil_tes_id', sa.Integer(), nullable=False),
        sa.Column('tingkat_seleksi_id', sa.Integer(), nullable=False),
        sa.Column('skor_aktual', sa.Numeric(precision=5, scale=2, asdecimal=False), nullable=False),
        sa.Column('passing_grade', sa.Numeric(precision=5, scale=2, asdecimal=False), nullable=False),
        sa.Column('lulus', sa.Boolean(), nullable=False),
        sa.Column('dievaluasi_pada', sa.DateTime(timezone=True), server_default=sa.text('(CURRENT_TIMESTAMP)'), nullable=False),
        sa.ForeignKeyConstraint(['hasil_tes_id'], ['hasil_tes.id'], name=op.f('fk_riwayat_evaluasi_pre_test_hasil_tes_id_hasil_tes'), ondelete='CASCADE'),
        sa.ForeignKeyConstraint(['tingkat_seleksi_id'], ['tingkat_seleksi.id'], name=op.f('fk_riwayat_evaluasi_pre_test_tingkat_seleksi_id_tingkat_seleksi'), ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('id', name=op.f('pk_riwayat_evaluasi_pre_test'))
    )


def downgrade() -> None:
    """Downgrade schema."""
    op.drop_table('riwayat_evaluasi_pre_test')
    op.drop_table('aturan_pre_test')
    op.drop_column('akses_tingkat_siswa', 'simulasi_terbuka')

