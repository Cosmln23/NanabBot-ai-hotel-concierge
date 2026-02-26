
"""Merge branches 0008 and 0013."""

revision = "c594d6938593"
down_revision = ("0008_add_food_beverage_task_type", "0013_auth_security_upgrade")
branch_labels = None
depends_on = None

from alembic import op  # noqa: E402
import sqlalchemy as sa  # noqa: E402


def upgrade() -> None:
    pass


def downgrade() -> None:
    pass
