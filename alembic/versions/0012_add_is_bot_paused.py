"""Add is_bot_paused to conversation

Revision ID: 0012_add_is_bot_paused
Revises: 0011_add_line_user_id
Create Date: 2025-12-09 00:00:00
"""
from alembic import op
import sqlalchemy as sa


revision = "0012_add_is_bot_paused"
down_revision = "0011_add_line_user_id"
branch_labels = None
depends_on = None


def upgrade() -> None:
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    existing_cols = {col["name"] for col in inspector.get_columns("conversation")}

    if "is_bot_paused" not in existing_cols:
        op.add_column(
            "conversation",
            sa.Column("is_bot_paused", sa.Boolean(), nullable=False, server_default=sa.false()),
        )

    # Ensure no server default remains (even if column pre-existed from earlier migration)
    op.alter_column("conversation", "is_bot_paused", server_default=None)


def downgrade() -> None:
    op.drop_column("conversation", "is_bot_paused")
