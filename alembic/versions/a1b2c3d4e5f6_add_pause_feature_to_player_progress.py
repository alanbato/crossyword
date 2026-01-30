"""add pause feature to player progress

Revision ID: a1b2c3d4e5f6
Revises: 4870865b00c4
Create Date: 2026-01-30 12:00:00.000000

"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = "a1b2c3d4e5f6"
down_revision: Union[str, Sequence[str], None] = "4870865b00c4"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Add pause-related columns to playerprogress table."""
    with op.batch_alter_table("playerprogress") as batch_op:
        batch_op.add_column(
            sa.Column("is_paused", sa.Boolean(), nullable=False, server_default="0")
        )
        batch_op.add_column(
            sa.Column(
                "accumulated_seconds", sa.Integer(), nullable=False, server_default="0"
            )
        )
        batch_op.add_column(sa.Column("pause_started_at", sa.DateTime(), nullable=True))


def downgrade() -> None:
    """Remove pause-related columns from playerprogress table."""
    with op.batch_alter_table("playerprogress") as batch_op:
        batch_op.drop_column("pause_started_at")
        batch_op.drop_column("accumulated_seconds")
        batch_op.drop_column("is_paused")
