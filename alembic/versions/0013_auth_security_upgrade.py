"""Auth security upgrade: owners, must_change_password, reset tokens

Revision ID: 0013_auth_security_upgrade
Revises: 0012_add_is_bot_paused
Create Date: 2025-12-09 01:00:00
"""
from alembic import op
import sqlalchemy as sa


revision = "0013_auth_security_upgrade"
down_revision = "0012_add_is_bot_paused"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "staff_user",
        sa.Column("must_change_password", sa.Boolean(), nullable=False, server_default=sa.true()),
    )
    op.alter_column("staff_user", "must_change_password", server_default=None)

    op.create_table(
        "platform_owner",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("email", sa.String(), nullable=False, unique=True),
        sa.Column("password_hash", sa.String(), nullable=False),
        sa.Column("is_active", sa.Boolean(), nullable=False, server_default=sa.true()),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
    )
    op.create_table(
        "password_reset_token",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("user_type", sa.String(), nullable=False),
        sa.Column("user_id", sa.Integer(), nullable=False),
        sa.Column("token", sa.String(), nullable=False),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
    )
    op.create_index("ix_password_reset_token_token", "password_reset_token", ["token"], unique=True)


def downgrade() -> None:
    op.drop_index("ix_password_reset_token_token", table_name="password_reset_token")
    op.drop_table("password_reset_token")
    op.drop_table("platform_owner")
    op.drop_column("staff_user", "must_change_password")
