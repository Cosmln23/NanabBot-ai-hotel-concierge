
"""Create system_setting table for platform-level secrets."""

from alembic import op
import sqlalchemy as sa
from sqlalchemy.sql import func


# revision identifiers, used by Alembic.
revision = "ed4feb8f0546"
down_revision = "b8cba32ae5a3"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "system_setting",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("key", sa.String(), nullable=False),
        sa.Column("value", sa.Text(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False),
    )
    op.create_unique_constraint("uq_system_setting_key", "system_setting", ["key"])


def downgrade() -> None:
    op.drop_constraint("uq_system_setting_key", "system_setting", type_="unique")
    op.drop_table("system_setting")
