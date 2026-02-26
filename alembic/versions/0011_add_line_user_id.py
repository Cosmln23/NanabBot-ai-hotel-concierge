"""Add line_user_id to guest

Revision ID: 0011_add_line_user_id
Revises: 0010_add_bot_paused
Create Date: 2025-12-09 00:00:00

"""
from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision = "0011_add_line_user_id"
down_revision = "0010_add_bot_paused"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("guest", sa.Column("line_user_id", sa.String(), nullable=True))
    op.create_index("ix_guest_line_user_id", "guest", ["line_user_id"], unique=True)


def downgrade() -> None:
    op.drop_index("ix_guest_line_user_id", table_name="guest")
    op.drop_column("guest", "line_user_id")
