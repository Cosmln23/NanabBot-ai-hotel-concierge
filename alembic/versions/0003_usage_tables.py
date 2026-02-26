"""add usage analytics tables"""

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision = "0003_usage_tables"
down_revision = "0002_journey_tables"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "usage_event",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("hotel_id", sa.Integer(), sa.ForeignKey("hotel.id"), nullable=False),
        sa.Column("event_type", sa.String(), nullable=False),
        sa.Column("value_int", sa.Integer(), nullable=False, server_default="1"),
        sa.Column("metadata_json", postgresql.JSONB(), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("now()"),
        ),
    )
    op.create_index("ix_usage_event_hotel_id", "usage_event", ["hotel_id"])

    op.create_table(
        "usage_daily",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("hotel_id", sa.Integer(), sa.ForeignKey("hotel.id"), nullable=False),
        sa.Column("date", sa.DateTime(timezone=False), nullable=False),
        sa.Column("messages_in", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("messages_out_bot", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("messages_out_staff", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("tasks_created", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("tasks_done", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("llm_calls", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("llm_tokens", sa.Integer(), nullable=False, server_default="0"),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("now()"),
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("now()"),
        ),
        sa.UniqueConstraint("hotel_id", "date", name="uq_usage_daily_hotel_date"),
    )
    op.create_index("ix_usage_daily_hotel_id", "usage_daily", ["hotel_id"])


def downgrade() -> None:
    op.drop_index("ix_usage_daily_hotel_id", table_name="usage_daily")
    op.drop_table("usage_daily")
    op.drop_index("ix_usage_event_hotel_id", table_name="usage_event")
    op.drop_table("usage_event")
