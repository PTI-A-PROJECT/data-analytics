"""anonymisasi hasil_tes (tiket 10)

Revision ID: 0002
Revises: 0001
Create Date: 2026-09-22 00:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '0002'
down_revision: Union[str, Sequence[str], None] = '0001'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    with op.batch_alter_table('hasil_tes', schema=None) as batch_op:
        batch_op.alter_column('siswa_id', existing_type=sa.Integer(), nullable=True)
        batch_op.add_column(
            sa.Column(
                'is_anonymized',
                sa.Boolean(),
                nullable=False,
                server_default=sa.false(),
            )
        )


def downgrade() -> None:
    """Downgrade schema."""
    with op.batch_alter_table('hasil_tes', schema=None) as batch_op:
        batch_op.drop_column('is_anonymized')
        batch_op.alter_column('siswa_id', existing_type=sa.Integer(), nullable=False)
