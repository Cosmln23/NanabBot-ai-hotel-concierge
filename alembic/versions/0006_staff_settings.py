"""add staff settings, task summary, pending confirmation"""

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision = "0006_staff_settings"
down_revision = "0005_hotel_ai_profile"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("hotel", sa.Column("staff_language", sa.String(length=5), nullable=True))
    op.add_column("hotel", sa.Column("staff_alert_phone", sa.String(), nullable=True))

    op.add_column("task", sa.Column("staff_summary", sa.Text(), nullable=True))
    op.add_column("task", sa.Column("priority", sa.String(), nullable=False, server_default="NORMAL"))

    op.add_column("conversation", sa.Column("pending_confirmation", sa.Text(), nullable=True))


def downgrade() -> None:
    op.drop_column("conversation", "pending_confirmation")
    op.drop_column("task", "priority")
    op.drop_column("task", "staff_summary")
    op.drop_column("hotel", "staff_alert_phone")
    op.drop_column("hotel", "staff_language")
