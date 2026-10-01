"""pensiunkan aturan_pemetaan (fase 2 issue 03)

Status Pemetaan fase 2 memakai satu ambang (aturan_adaptif.ambang_lemah);
ambang cukup & representasi fase 1 tidak dipakai lagi. Tabel berisi konfigurasi
saja (bukan data siswa). hasil_tes_subkompetensi & jawaban_siswa (riwayat fase
1) tetap disimpan.

Revision ID: 0009
Revises: 0008
Create Date: 2026-09-29 12:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '0009'
down_revision: Union[str, Sequence[str], None] = '0008'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    op.drop_table('aturan_pemetaan')


def downgrade() -> None:
    """Downgrade schema — tabel dibuat ulang kosong (default di-seed ulang
    otomatis oleh kode fase 1 saat dipakai)."""
    op.create_table('aturan_pemetaan',
    sa.Column('id', sa.Integer(), nullable=False),
    sa.Column('tingkat_seleksi_id', sa.String(), nullable=False),
    sa.Column('ambang_cukup_persen', sa.Numeric(precision=5, scale=2, asdecimal=False), nullable=False),
    sa.Column('ambang_representasi_persen', sa.Numeric(precision=5, scale=2, asdecimal=False), nullable=False),
    sa.CheckConstraint('ambang_cukup_persen >= 0 AND ambang_cukup_persen <= 100', name=op.f('ck_aturan_pemetaan_ck_aturan_pemetaan_ambang_cukup_rentang')),
    sa.CheckConstraint('ambang_representasi_persen >= 0 AND ambang_representasi_persen <= 100', name=op.f('ck_aturan_pemetaan_ck_aturan_pemetaan_ambang_representasi_rentang')),
    sa.PrimaryKeyConstraint('id', name=op.f('pk_aturan_pemetaan')),
    sa.UniqueConstraint('tingkat_seleksi_id', name=op.f('uq_aturan_pemetaan_tingkat_seleksi_id'))
    )
