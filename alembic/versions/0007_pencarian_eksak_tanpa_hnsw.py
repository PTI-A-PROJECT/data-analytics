"""pencarian eksak tanpa hnsw (fase 2 issue 01)

Pencarian soal mirip selalu difilter (tingkat, materi, level) yang menyisakan
puluhan soal. Kalau planner memilih index HNSW, hasilnya approximate dan filter
diterapkan setelah mengambil kandidat global, sehingga soal paling mirip bisa
terlewat. Pada 1.800 soal planner sudah memilih B-tree + jarak eksak (~2 ms,
diukur); menghapus HNSW menjamin perilaku eksak itu tetap berlaku saat data
atau statistik berubah, dan meniadakan biaya perawatan index.

Revision ID: 0007
Revises: 0006
Create Date: 2026-09-29 10:00:00.000000

"""
from typing import Sequence, Union

from alembic import op


# revision identifiers, used by Alembic.
revision: str = '0007'
down_revision: Union[str, Sequence[str], None] = '0006'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    op.drop_index('ix_soal_embedding_hnsw', table_name='soal')
    op.drop_index('ix_materi_embedding_hnsw', table_name='materi')


def downgrade() -> None:
    """Downgrade schema."""
    op.create_index('ix_materi_embedding_hnsw', 'materi', ['embedding'], postgresql_using='hnsw', postgresql_ops={'embedding': 'vector_cosine_ops'})
    op.create_index('ix_soal_embedding_hnsw', 'soal', ['embedding'], postgresql_using='hnsw', postgresql_ops={'embedding': 'vector_cosine_ops'})
