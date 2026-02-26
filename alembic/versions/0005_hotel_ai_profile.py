"""add hotel ai profile table"""

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = "0005_hotel_ai_profile"
down_revision = "0004_hotel_integrations"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "hotel_ai_profile",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("hotel_id", sa.Integer(), sa.ForeignKey("hotel.id"), nullable=False),
        sa.Column("bot_name", sa.String(), nullable=True),
        sa.Column("tone", sa.String(), nullable=True),
        sa.Column("use_emojis", sa.Boolean(), nullable=False, server_default=sa.text("true")),
        sa.Column("max_reply_sentences", sa.Integer(), nullable=False, server_default="2"),
        sa.Column("primary_language", sa.String(length=5), nullable=True),
        sa.Column("reply_in_guest_language", sa.Boolean(), nullable=False, server_default=sa.text("true")),
        sa.Column("wifi_ssid", sa.String(), nullable=True),
        sa.Column("wifi_password", sa.String(), nullable=True),
        sa.Column("breakfast_hours", sa.Text(), nullable=True),
        sa.Column("parking_info", sa.Text(), nullable=True),
        sa.Column("late_checkout_policy", sa.Text(), nullable=True),
        sa.Column("custom_instructions", sa.Text(), nullable=True),
        sa.UniqueConstraint("hotel_id", name="uq_hotel_ai_profile_hotel_id"),
    )
    op.create_index("ix_hotel_ai_profile_hotel_id", "hotel_ai_profile", ["hotel_id"], unique=True)


def downgrade() -> None:
    op.drop_index("ix_hotel_ai_profile_hotel_id", table_name="hotel_ai_profile")
    op.drop_table("hotel_ai_profile")
