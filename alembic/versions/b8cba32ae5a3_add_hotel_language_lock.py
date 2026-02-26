
"""Add interface_language and language_locked to hotel."""

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = "b8cba32ae5a3"
down_revision = "0c1f115d767b"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "hotel",
        sa.Column("interface_language", sa.String(), nullable=False, server_default="en"),
    )
    op.add_column(
        "hotel",
        sa.Column("language_locked", sa.Boolean(), nullable=False, server_default=sa.false()),
    )
    # Drop server defaults if desired (to avoid future default issues)
    op.alter_column("hotel", "interface_language", server_default=None)
    op.alter_column("hotel", "language_locked", server_default=None)


def downgrade() -> None:
    op.drop_column("hotel", "language_locked")
    op.drop_column("hotel", "interface_language")
