"""add hotel settings json for agent config"""
from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision = "0007_llm_agent_settings"
down_revision = "0006_staff_settings"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("hotel", sa.Column("settings", sa.JSON(), nullable=True))


def downgrade() -> None:
    op.drop_column("hotel", "settings")
