"""Add subscription and billing fields to hotel and conversation.

Adds:
- hotel.country (ISO 3166-1 alpha-2)
- hotel.subscription_tier (free/basic/pro)
- hotel.trial_ends_at
- hotel.stripe_customer_id
- conversation.last_qr_scan_at (for QR cooldown anti-abuse)
"""

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = "0015_subscription"
down_revision = "ed4feb8f0546"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # Hotel subscription fields
    op.add_column(
        "hotel",
        sa.Column("country", sa.String(2), nullable=True),
    )
    op.add_column(
        "hotel",
        sa.Column("subscription_tier", sa.String(20), nullable=False, server_default="free"),
    )
    op.add_column(
        "hotel",
        sa.Column("trial_ends_at", sa.DateTime(timezone=True), nullable=True),
    )
    op.add_column(
        "hotel",
        sa.Column("stripe_customer_id", sa.String(100), nullable=True),
    )

    # Drop server default for subscription_tier (keep in model only)
    op.alter_column("hotel", "subscription_tier", server_default=None)

    # Conversation QR cooldown field
    op.add_column(
        "conversation",
        sa.Column("last_qr_scan_at", sa.DateTime(timezone=True), nullable=True),
    )


def downgrade() -> None:
    op.drop_column("conversation", "last_qr_scan_at")
    op.drop_column("hotel", "stripe_customer_id")
    op.drop_column("hotel", "trial_ends_at")
    op.drop_column("hotel", "subscription_tier")
    op.drop_column("hotel", "country")
