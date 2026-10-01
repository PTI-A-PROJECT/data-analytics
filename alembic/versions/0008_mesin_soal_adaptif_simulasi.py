"""mesin soal adaptif simulasi (fase 2 issue 03)

Parameter simulasi adaptif di aturan_adaptif, seed pengacakan & satu simulasi
aktif per siswa per tingkat di paket_tes, serta level_target / level_aktual /
alasan per soal di paket_tes_soal.

Revision ID: 0008
Revises: 0007
Create Date: 2026-09-29 10:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '0008'
down_revision: Union[str, Sequence[str], None] = '0007'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

_ENUM_LEVEL = sa.Enum('mudah', 'menengah', 'sulit', name='levelsoal', native_enum=False)
_ENUM_ALASAN = sa.Enum(
    'vektor_mirip', 'acak', 'fallback_level', 'fallback_ulang',
    name='alasanpilihsoal', native_enum=False,
)


def upgrade() -> None:
    """Upgrade schema."""
    with op.batch_alter_table('aturan_adaptif', schema=None) as batch_op:
        batch_op.add_column(sa.Column('jumlah_soal_simulasi', sa.Integer(), server_default='30', nullable=False))
        batch_op.add_column(sa.Column('kuota_min', sa.Integer(), server_default='2', nullable=False))
        batch_op.add_column(sa.Column('bobot_lemah', sa.Integer(), server_default='3', nullable=False))
        batch_op.add_column(sa.Column('ambang_naik', sa.Numeric(precision=5, scale=2, asdecimal=False), server_default='80', nullable=False))
        batch_op.create_check_constraint(op.f('ck_aturan_adaptif_ck_aturan_adaptif_jumlah_simulasi_positif'), 'jumlah_soal_simulasi > 0')
        batch_op.create_check_constraint(op.f('ck_aturan_adaptif_ck_aturan_adaptif_kuota_min_positif'), 'kuota_min >= 1')
        batch_op.create_check_constraint(op.f('ck_aturan_adaptif_ck_aturan_adaptif_bobot_lemah_min'), 'bobot_lemah >= 1')
        batch_op.create_check_constraint(op.f('ck_aturan_adaptif_ck_aturan_adaptif_ambang_naik_rentang'), 'ambang_lemah < ambang_naik AND ambang_naik <= 100')

    with op.batch_alter_table('paket_tes', schema=None) as batch_op:
        batch_op.add_column(sa.Column('seed', sa.BigInteger(), nullable=True))
        batch_op.create_index('uq_paket_tes_simulasi_aktif_per_siswa_tingkat', ['siswa_id', 'tingkat_seleksi_id'], unique=True, postgresql_where=sa.text("jenis_tes = 'simulasi' AND disubmit_pada IS NULL"))

    with op.batch_alter_table('paket_tes_soal', schema=None) as batch_op:
        batch_op.alter_column('level', new_column_name='level_aktual')
        # Semua paket sebelum issue 03 adalah pre-test: target Mudah, dipilih acak.
        batch_op.add_column(sa.Column('level_target', _ENUM_LEVEL, server_default='mudah', nullable=False))
        batch_op.add_column(sa.Column('alasan', _ENUM_ALASAN, server_default='acak', nullable=False))
    with op.batch_alter_table('paket_tes_soal', schema=None) as batch_op:
        batch_op.alter_column('level_target', server_default=None)
        batch_op.alter_column('alasan', server_default=None)


def downgrade() -> None:
    """Downgrade schema."""
    with op.batch_alter_table('paket_tes_soal', schema=None) as batch_op:
        batch_op.drop_column('alasan')
        batch_op.drop_column('level_target')
        batch_op.alter_column('level_aktual', new_column_name='level')

    with op.batch_alter_table('paket_tes', schema=None) as batch_op:
        batch_op.drop_index('uq_paket_tes_simulasi_aktif_per_siswa_tingkat', postgresql_where=sa.text("jenis_tes = 'simulasi' AND disubmit_pada IS NULL"))
        batch_op.drop_column('seed')

    with op.batch_alter_table('aturan_adaptif', schema=None) as batch_op:
        batch_op.drop_constraint(op.f('ck_aturan_adaptif_ck_aturan_adaptif_ambang_naik_rentang'), type_='check')
        batch_op.drop_constraint(op.f('ck_aturan_adaptif_ck_aturan_adaptif_bobot_lemah_min'), type_='check')
        batch_op.drop_constraint(op.f('ck_aturan_adaptif_ck_aturan_adaptif_kuota_min_positif'), type_='check')
        batch_op.drop_constraint(op.f('ck_aturan_adaptif_ck_aturan_adaptif_jumlah_simulasi_positif'), type_='check')
        batch_op.drop_column('ambang_naik')
        batch_op.drop_column('bobot_lemah')
        batch_op.drop_column('kuota_min')
        batch_op.drop_column('jumlah_soal_simulasi')
