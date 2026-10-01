"""bank konten pgvector (fase 2 issue 01)

Ganti katalog seed fase 1 (kompetensi/subkompetensi/soal) dengan bank konten
fase 2: materi, halaman_materi, soal ber-embedding pgvector. Sediakan baris
tingkat_seleksi Kabupaten & Provinsi (dulu diisi scripts/seed yang sudah
dihapus). Lihat docs/adr/0004.

Revision ID: 0005
Revises: 0004
Create Date: 2026-09-28 10:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
from pgvector.sqlalchemy import Vector
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql


# revision identifiers, used by Alembic.
revision: str = '0005'
down_revision: Union[str, Sequence[str], None] = '0004'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

DIMENSI_EMBEDDING = 384


def upgrade() -> None:
    """Upgrade schema."""
    op.execute("CREATE EXTENSION IF NOT EXISTS vector")

    op.drop_table('soal')
    op.drop_table('subkompetensi')
    op.drop_table('kompetensi')

    op.create_table('materi',
    sa.Column('id', sa.String(), nullable=False),
    sa.Column('tingkat_seleksi_id', sa.Integer(), nullable=False),
    sa.Column('judul', sa.String(), nullable=False),
    sa.Column('embedding', Vector(DIMENSI_EMBEDDING), nullable=False),
    sa.Column('hash_konten', sa.String(), nullable=False),
    sa.ForeignKeyConstraint(['tingkat_seleksi_id'], ['tingkat_seleksi.id'], name=op.f('fk_materi_tingkat_seleksi_id_tingkat_seleksi'), ondelete='CASCADE'),
    sa.PrimaryKeyConstraint('id', name=op.f('pk_materi'))
    )
    op.create_index(op.f('ix_materi_tingkat_seleksi_id'), 'materi', ['tingkat_seleksi_id'])
    op.create_index('ix_materi_embedding_hnsw', 'materi', ['embedding'], postgresql_using='hnsw', postgresql_ops={'embedding': 'vector_cosine_ops'})

    op.create_table('halaman_materi',
    sa.Column('id', sa.Integer(), nullable=False),
    sa.Column('materi_id', sa.String(), nullable=False),
    sa.Column('nomor', sa.Integer(), nullable=False),
    sa.Column('konten', sa.String(), nullable=False),
    sa.CheckConstraint('nomor >= 1', name=op.f('ck_halaman_materi_ck_halaman_materi_nomor_positif')),
    sa.ForeignKeyConstraint(['materi_id'], ['materi.id'], name=op.f('fk_halaman_materi_materi_id_materi'), ondelete='CASCADE'),
    sa.PrimaryKeyConstraint('id', name=op.f('pk_halaman_materi')),
    sa.UniqueConstraint('materi_id', 'nomor', name=op.f('uq_halaman_materi_materi_id'))
    )

    op.create_table('soal',
    sa.Column('id', sa.String(), nullable=False),
    sa.Column('materi_id', sa.String(), nullable=False),
    sa.Column('tingkat_seleksi_id', sa.Integer(), nullable=False),
    sa.Column('pertanyaan', sa.String(), nullable=False),
    sa.Column('pilihan_jawaban', postgresql.JSONB(astext_type=sa.Text()), nullable=False),
    sa.Column('kunci_jawaban', sa.String(), nullable=False),
    sa.Column('pembahasan', sa.String(), nullable=True),
    sa.Column('level', sa.Enum('mudah', 'menengah', 'sulit', name='levelsoal', native_enum=False), nullable=False),
    sa.Column('embedding', Vector(DIMENSI_EMBEDDING), nullable=False),
    sa.Column('hash_konten', sa.String(), nullable=False),
    sa.ForeignKeyConstraint(['materi_id'], ['materi.id'], name=op.f('fk_soal_materi_id_materi'), ondelete='CASCADE'),
    sa.ForeignKeyConstraint(['tingkat_seleksi_id'], ['tingkat_seleksi.id'], name=op.f('fk_soal_tingkat_seleksi_id_tingkat_seleksi'), ondelete='CASCADE'),
    sa.PrimaryKeyConstraint('id', name=op.f('pk_soal'))
    )
    op.create_index('ix_soal_tingkat_materi_level', 'soal', ['tingkat_seleksi_id', 'materi_id', 'level'])
    op.create_index('ix_soal_embedding_hnsw', 'soal', ['embedding'], postgresql_using='hnsw', postgresql_ops={'embedding': 'vector_cosine_ops'})

    # Data referensi — idempoten terhadap database yang dulu sudah di-seed
    # (scripts/seed fase 1 mengisi urutan 1..3 dengan nama yang sama).
    op.execute(
        "INSERT INTO tingkat_seleksi (nama, urutan) VALUES "
        "('Kabupaten', 1), ('Provinsi', 2) "
        "ON CONFLICT (urutan) DO NOTHING"
    )


def downgrade() -> None:
    """Downgrade schema."""
    op.drop_index('ix_soal_embedding_hnsw', table_name='soal')
    op.drop_index('ix_soal_tingkat_materi_level', table_name='soal')
    op.drop_table('soal')
    op.drop_table('halaman_materi')
    op.drop_index('ix_materi_embedding_hnsw', table_name='materi')
    op.drop_index(op.f('ix_materi_tingkat_seleksi_id'), table_name='materi')
    op.drop_table('materi')

    op.create_table('kompetensi',
    sa.Column('id', sa.Integer(), nullable=False),
    sa.Column('nama', sa.String(), nullable=False),
    sa.Column('deskripsi', sa.String(), nullable=True),
    sa.PrimaryKeyConstraint('id', name=op.f('pk_kompetensi'))
    )
    op.create_table('subkompetensi',
    sa.Column('id', sa.Integer(), nullable=False),
    sa.Column('kompetensi_id', sa.Integer(), nullable=False),
    sa.Column('nama', sa.String(), nullable=False),
    sa.Column('deskripsi', sa.String(), nullable=True),
    sa.ForeignKeyConstraint(['kompetensi_id'], ['kompetensi.id'], name=op.f('fk_subkompetensi_kompetensi_id_kompetensi'), ondelete='CASCADE'),
    sa.PrimaryKeyConstraint('id', name=op.f('pk_subkompetensi'))
    )
    op.create_table('soal',
    sa.Column('id', sa.Integer(), nullable=False),
    sa.Column('subkompetensi_id', sa.Integer(), nullable=False),
    sa.Column('tingkat_seleksi_id', sa.Integer(), nullable=False),
    sa.Column('nomor', sa.Integer(), nullable=False),
    sa.Column('pertanyaan', sa.String(), nullable=False),
    sa.Column('pilihan_jawaban', sa.JSON(), nullable=False),
    sa.Column('kunci_jawaban', sa.String(), nullable=False),
    sa.Column('batas_waktu_detik', sa.Integer(), server_default='60', nullable=False),
    sa.ForeignKeyConstraint(['subkompetensi_id'], ['subkompetensi.id'], name=op.f('fk_soal_subkompetensi_id_subkompetensi'), ondelete='CASCADE'),
    sa.ForeignKeyConstraint(['tingkat_seleksi_id'], ['tingkat_seleksi.id'], name=op.f('fk_soal_tingkat_seleksi_id_tingkat_seleksi'), ondelete='CASCADE'),
    sa.PrimaryKeyConstraint('id', name=op.f('pk_soal')),
    sa.UniqueConstraint('tingkat_seleksi_id', 'nomor', name=op.f('uq_soal_tingkat_seleksi_id'))
    )
    # Baris tingkat_seleksi & extension vector sengaja tidak dihapus: tingkat
    # mungkin sudah dirujuk akses_tingkat_siswa/aturan_kenaikan_tingkat.
