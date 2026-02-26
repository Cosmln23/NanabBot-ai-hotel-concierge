"""add security_pin to hotel

Revision ID: 0014_add_security_pin
Revises: c594d6938593
Create Date: 2025-02-XX
"""

from alembic import op
import sqlalchemy as sa
import random


# revision identifiers, used by Alembic.
revision = "0014_add_security_pin"
down_revision = "c594d6938593"
branch_labels = None
depends_on = None


def _generate_pin() -> str:
    return f"{random.randint(0, 9999):04d}"


def upgrade():
    op.add_column("hotel", sa.Column("security_pin", sa.String(), nullable=True))
    conn = op.get_bind()
    res = conn.execute(sa.text("SELECT id FROM hotel")).fetchall()
    for row in res:
        pin = _generate_pin()
        conn.execute(sa.text("UPDATE hotel SET security_pin=:pin WHERE id=:id"), {"pin": pin, "id": row.id})


def downgrade():
    op.drop_column("hotel", "security_pin")
