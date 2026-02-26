"""add FOOD_BEVERAGE to task_type enum"""
from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision = "0008_add_food_beverage_task_type"
down_revision = "0007_llm_agent_settings"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # Add FOOD_BEVERAGE value to task_type enum
    # Using IF NOT EXISTS to make migration idempotent
    op.execute("""
        DO $$
        BEGIN
            IF NOT EXISTS (
                SELECT 1 FROM pg_enum
                WHERE enumlabel = 'FOOD_BEVERAGE'
                AND enumtypid = (SELECT oid FROM pg_type WHERE typname = 'task_type')
            ) THEN
                ALTER TYPE task_type ADD VALUE 'FOOD_BEVERAGE';
            END IF;
        END
        $$;
    """)


def downgrade() -> None:
    # Cannot safely remove enum value in PostgreSQL
    # Would require recreating the entire enum and migrating all data
    # which is not safe in production
    pass
