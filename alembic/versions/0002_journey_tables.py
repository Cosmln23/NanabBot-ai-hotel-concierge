"""add journey tables and whatsapp opt-in"""

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision = "0002_journey_tables"
down_revision = "0001_initial"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("stay", sa.Column("whatsapp_opt_in", sa.Boolean(), nullable=False, server_default=sa.text("true")))

    op.create_table(
        "journey",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("hotel_id", sa.Integer(), sa.ForeignKey("hotel.id"), nullable=False),
        sa.Column("name", sa.String(), nullable=False),
        sa.Column("type", sa.String(), nullable=False),
        sa.Column("delay_minutes", sa.Integer(), nullable=False, server_default="20"),
        sa.Column("is_active", sa.Boolean(), nullable=False, server_default=sa.text("true")),
        sa.Column("template_key", sa.String(), nullable=False),
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
    )
    op.create_index("ix_journey_hotel_id", "journey", ["hotel_id"])

    journey_event_status = sa.Enum("PENDING", "SENT", "CANCELLED", name="journey_event_status")

    op.create_table(
        "journey_event",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("hotel_id", sa.Integer(), sa.ForeignKey("hotel.id"), nullable=False),
        sa.Column("journey_id", sa.Integer(), sa.ForeignKey("journey.id"), nullable=False),
        sa.Column("guest_id", sa.Integer(), sa.ForeignKey("guest.id"), nullable=False),
        sa.Column("stay_id", sa.Integer(), sa.ForeignKey("stay.id"), nullable=False),
        sa.Column("channel", sa.String(), nullable=False, server_default="whatsapp"),
        sa.Column("run_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("status", journey_event_status, nullable=False, server_default="PENDING"),
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
    )
    op.create_index("ix_journey_event_hotel_id", "journey_event", ["hotel_id"])
    op.create_index("ix_journey_event_journey_id", "journey_event", ["journey_id"])
    op.create_index("ix_journey_event_guest_id", "journey_event", ["guest_id"])
    op.create_index("ix_journey_event_stay_id", "journey_event", ["stay_id"])


def downgrade() -> None:
    op.drop_index("ix_journey_event_stay_id", table_name="journey_event")
    op.drop_index("ix_journey_event_guest_id", table_name="journey_event")
    op.drop_index("ix_journey_event_journey_id", table_name="journey_event")
    op.drop_index("ix_journey_event_hotel_id", table_name="journey_event")
    op.drop_table("journey_event")

    op.drop_index("ix_journey_hotel_id", table_name="journey")
    op.drop_table("journey")

    op.drop_column("stay", "whatsapp_opt_in")

    sa.Enum(name="journey_event_status").drop(op.get_bind(), checkfirst=True)
