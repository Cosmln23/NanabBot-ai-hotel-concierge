"""Add is_bot_paused to Conversation

Revision ID: 0010_add_bot_paused
Revises: 0008_add_food_beverage_task_type
Create Date: 2025-12-07 20:05:00

"""
from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision = '0010_add_bot_paused'
down_revision = "0008_add_food_beverage_task_type"
branch_labels = None
depends_on = None


def upgrade():
    op.add_column('conversation', sa.Column('is_bot_paused', sa.Boolean(), nullable=False, server_default='false'))


def downgrade():
    op.drop_column('conversation', 'is_bot_paused')
