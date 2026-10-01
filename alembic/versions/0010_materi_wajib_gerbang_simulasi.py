"""materi wajib gerbang simulasi (fase 2 issue 04)

Materi Wajib per attempt (+ halaman yang dibuka sejak diwajibkan) dan riwayat
baca halaman permanen (navigasi bebas). progress_materi fase 1 (high-water
mark, id int dari katalog fullstack yang tidak bisa dipetakan ke Materi fase 2)
TIDAK dihapus: diarsipkan sebagai progress_materi_fase1 dan diabaikan
autogenerate (alembic/env.py).

Revision ID: 0010
Revises: 0009
Create Date: 2026-09-29 14:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '0010'
down_revision: Union[str, Sequence[str], None] = '0009'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    op.rename_table('progress_materi', 'progress_materi_fase1')

    op.create_table('riwayat_baca_halaman',
    sa.Column('id', sa.Integer(), nullable=False),
    sa.Column('siswa_id', sa.String(), nullable=False),
    sa.Column('materi_id', sa.String(), nullable=False),
    sa.Column('nomor_halaman', sa.Integer(), nullable=False),
    sa.Column('pertama_dibuka_pada', sa.DateTime(timezone=True), nullable=False),
    sa.Column('terakhir_dibuka_pada', sa.DateTime(timezone=True), nullable=False),
    sa.ForeignKeyConstraint(['materi_id'], ['materi.id'], name=op.f('fk_riwayat_baca_halaman_materi_id_materi'), ondelete='CASCADE'),
    sa.PrimaryKeyConstraint('id', name=op.f('pk_riwayat_baca_halaman')),
    sa.UniqueConstraint('siswa_id', 'materi_id', 'nomor_halaman', name='uq_riwayat_baca_halaman_siswa_materi')
    )
    op.create_table('materi_wajib',
    sa.Column('id', sa.Integer(), nullable=False),
    sa.Column('paket_tes_id', sa.Integer(), nullable=False),
    sa.Column('siswa_id', sa.String(), nullable=False),
    sa.Column('tingkat_seleksi_id', sa.Integer(), nullable=False),
    sa.Column('materi_id', sa.String(), nullable=False),
    sa.Column('urutan', sa.Integer(), nullable=False),
    sa.Column('akurasi', sa.Numeric(precision=5, scale=2, asdecimal=False), nullable=False),
    sa.Column('dibuat_pada', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
    sa.Column('selesai_pada', sa.DateTime(timezone=True), nullable=True),
    sa.ForeignKeyConstraint(['materi_id'], ['materi.id'], name=op.f('fk_materi_wajib_materi_id_materi'), ondelete='CASCADE'),
    sa.ForeignKeyConstraint(['paket_tes_id'], ['paket_tes.id'], name=op.f('fk_materi_wajib_paket_tes_id_paket_tes'), ondelete='CASCADE'),
    sa.ForeignKeyConstraint(['tingkat_seleksi_id'], ['tingkat_seleksi.id'], name=op.f('fk_materi_wajib_tingkat_seleksi_id_tingkat_seleksi'), ondelete='CASCADE'),
    sa.PrimaryKeyConstraint('id', name=op.f('pk_materi_wajib')),
    sa.UniqueConstraint('paket_tes_id', 'materi_id', name='uq_materi_wajib_paket_materi')
    )
    op.create_index('ix_materi_wajib_siswa_materi', 'materi_wajib', ['siswa_id', 'materi_id'], unique=False)
    op.create_table('materi_wajib_halaman',
    sa.Column('id', sa.Integer(), nullable=False),
    sa.Column('materi_wajib_id', sa.Integer(), nullable=False),
    sa.Column('nomor_halaman', sa.Integer(), nullable=False),
    sa.Column('dibuka_pada', sa.DateTime(timezone=True), nullable=False),
    sa.ForeignKeyConstraint(['materi_wajib_id'], ['materi_wajib.id'], name=op.f('fk_materi_wajib_halaman_materi_wajib_id_materi_wajib'), ondelete='CASCADE'),
    sa.PrimaryKeyConstraint('id', name=op.f('pk_materi_wajib_halaman')),
    sa.UniqueConstraint('materi_wajib_id', 'nomor_halaman', name='uq_materi_wajib_halaman_wajib_nomor')
    )


def downgrade() -> None:
    """Downgrade schema."""
    op.drop_table('materi_wajib_halaman')
    op.drop_index('ix_materi_wajib_siswa_materi', table_name='materi_wajib')
    op.drop_table('materi_wajib')
    op.drop_table('riwayat_baca_halaman')
    op.rename_table('progress_materi_fase1', 'progress_materi')
