"""add hotel integration fields"""

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = "0004_hotel_integrations"
down_revision = "0003_usage_tables"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("hotel", sa.Column("pms_type", sa.String(), nullable=True))
    op.add_column("hotel", sa.Column("pms_api_key", sa.String(), nullable=True))
    op.add_column("hotel", sa.Column("pms_property_id", sa.String(), nullable=True))
    op.add_column("hotel", sa.Column("whatsapp_phone_id", sa.String(), nullable=True))
    op.add_column("hotel", sa.Column("whatsapp_business_account_id", sa.String(), nullable=True))
    op.add_column("hotel", sa.Column("whatsapp_access_token", sa.String(), nullable=True))


def downgrade() -> None:
    op.drop_column("hotel", "whatsapp_access_token")
    op.drop_column("hotel", "whatsapp_business_account_id")
    op.drop_column("hotel", "whatsapp_phone_id")
    op.drop_column("hotel", "pms_property_id")
    op.drop_column("hotel", "pms_api_key")
    op.drop_column("hotel", "pms_type")
