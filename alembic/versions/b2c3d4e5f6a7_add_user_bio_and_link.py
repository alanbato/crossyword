"""add user bio and link fields

Revision ID: b2c3d4e5f6a7
Revises: a1b2c3d4e5f6
Create Date: 2026-01-30 14:00:00.000000

"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = "b2c3d4e5f6a7"
down_revision: Union[str, Sequence[str], None] = "a1b2c3d4e5f6"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Add bio and link columns to user table."""
    with op.batch_alter_table("user") as batch_op:
        batch_op.add_column(sa.Column("bio", sa.String(), nullable=True))
        batch_op.add_column(sa.Column("link", sa.String(), nullable=True))


def downgrade() -> None:
    """Remove bio and link columns from user table."""
    with op.batch_alter_table("user") as batch_op:
        batch_op.drop_column("link")
        batch_op.drop_column("bio")
