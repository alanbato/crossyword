"""add_user_use_colors_field

Revision ID: 4870865b00c4
Revises: bb2f24bf1dff
Create Date: 2026-01-27 17:35:13.905383

"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = "4870865b00c4"
down_revision: Union[str, Sequence[str], None] = "bb2f24bf1dff"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Add use_colors column to user table."""
    with op.batch_alter_table("user") as batch_op:
        batch_op.add_column(
            sa.Column("use_colors", sa.Boolean(), nullable=False, server_default="0")
        )


def downgrade() -> None:
    """Remove use_colors column from user table."""
    with op.batch_alter_table("user") as batch_op:
        batch_op.drop_column("use_colors")
