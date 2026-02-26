
"""Add per-hotel unique constraint for line_user_id."""

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = "0c1f115d767b"
down_revision = "0014_add_security_pin"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # Remove global unique index on line_user_id if present
    try:
        op.drop_index("ix_guest_line_user_id", table_name="guest")
    except Exception:
        # index might not exist on some databases; ignore
        pass
    # Add composite unique constraint (hotel_id, line_user_id)
    op.create_unique_constraint(
        "uq_guest_hotel_line_user",
        "guest",
        ["hotel_id", "line_user_id"],
    )
    # Optional supporting index on line_user_id for lookups
    op.create_index(
        "ix_guest_line_user_id",
        "guest",
        ["line_user_id"],
        unique=False,
    )


def downgrade() -> None:
    op.drop_index("ix_guest_line_user_id", table_name="guest")
    op.drop_constraint("uq_guest_hotel_line_user", "guest", type_="unique")
    # restore previous global unique index
    op.create_index(
        "ix_guest_line_user_id",
        "guest",
        ["line_user_id"],
        unique=True,
    )
