"""add_puzzle_source_and_original_date

Revision ID: bb2f24bf1dff
Revises:
Create Date: 2026-01-24 23:00:11.247315

"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = "bb2f24bf1dff"
down_revision: Union[str, Sequence[str], None] = None
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Add source and original_date columns to puzzle table."""
    with op.batch_alter_table("puzzle") as batch_op:
        batch_op.add_column(sa.Column("source", sa.String(), nullable=True))
        batch_op.add_column(sa.Column("original_date", sa.Date(), nullable=True))


def downgrade() -> None:
    """Remove source and original_date columns from puzzle table."""
    with op.batch_alter_table("puzzle") as batch_op:
        batch_op.drop_column("original_date")
        batch_op.drop_column("source")
