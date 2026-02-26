"""initial schema"""

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql
import pgvector.sqlalchemy

# revision identifiers, used by Alembic.
revision = "0001_initial"
down_revision = None
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute("CREATE EXTENSION IF NOT EXISTS vector")

    stay_status = sa.Enum(
        "PRE_STAY", "IN_HOUSE", "POST_STAY", "CANCELLED", name="stay_status"
    )
    conversation_status = sa.Enum(
        "OPEN", "ASSIGNED_TO_STAFF", "CLOSED", name="conversation_status"
    )
    message_sender = sa.Enum("GUEST", "BOT", "STAFF", name="message_sender")
    message_direction = sa.Enum("INCOMING", "OUTGOING", name="message_direction")
    task_status = sa.Enum("OPEN", "IN_PROGRESS", "DONE", "CANCELLED", name="task_status")
    task_type = sa.Enum("HOUSEKEEPING", "MAINTENANCE", "LOST_AND_FOUND", "OTHER", name="task_type")

    op.create_table(
        "hotel",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("name", sa.String(), nullable=False),
        sa.Column("timezone", sa.String(), nullable=False, server_default="UTC"),
        sa.Column("is_active", sa.Boolean(), nullable=False, server_default=sa.text("true")),
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

    op.create_table(
        "guest",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("hotel_id", sa.Integer(), sa.ForeignKey("hotel.id"), nullable=False),
        sa.Column("phone_hash", sa.String(), nullable=False),
        sa.Column("preferred_language", sa.String(), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("now()"),
        ),
        sa.UniqueConstraint("hotel_id", "phone_hash", name="uq_guest_hotel_phone"),
    )
    op.create_index("ix_guest_hotel_id", "guest", ["hotel_id"])

    op.create_table(
        "guest_pii",
        sa.Column("guest_id", sa.Integer(), sa.ForeignKey("guest.id"), primary_key=True),
        sa.Column("full_name", sa.String(), nullable=True),
        sa.Column("phone_plain", sa.String(), nullable=True),
        sa.Column("email_plain", sa.String(), nullable=True),
        sa.Column("other_pii_json", postgresql.JSONB(), nullable=True),
    )

    op.create_table(
        "room",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("hotel_id", sa.Integer(), sa.ForeignKey("hotel.id"), nullable=False),
        sa.Column("room_number", sa.String(), nullable=False),
        sa.Column("floor", sa.String(), nullable=True),
        sa.Column("type", sa.String(), nullable=True),
        sa.Column("is_active", sa.Boolean(), nullable=False, server_default=sa.text("true")),
    )
    op.create_index("ix_room_hotel_id", "room", ["hotel_id"])

    op.create_table(
        "stay",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("hotel_id", sa.Integer(), sa.ForeignKey("hotel.id"), nullable=False),
        sa.Column("guest_id", sa.Integer(), sa.ForeignKey("guest.id"), nullable=False),
        sa.Column("room_id", sa.Integer(), sa.ForeignKey("room.id"), nullable=True),
        sa.Column("checkin_date", sa.DateTime(timezone=True), nullable=False),
        sa.Column("checkout_date", sa.DateTime(timezone=True), nullable=False),
        sa.Column(
            "status",
            stay_status,
            nullable=False,
            server_default=sa.text("'PRE_STAY'::stay_status"),
        ),
        sa.Column("channel", sa.String(), nullable=True),
        sa.Column("pms_reservation_id", sa.String(), nullable=True),
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
    op.create_index("ix_stay_hotel_id", "stay", ["hotel_id"])
    op.create_index("ix_stay_guest_id", "stay", ["guest_id"])
    op.create_index("ix_stay_room_id", "stay", ["room_id"])

    op.create_table(
        "conversation",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("hotel_id", sa.Integer(), sa.ForeignKey("hotel.id"), nullable=False),
        sa.Column("guest_id", sa.Integer(), sa.ForeignKey("guest.id"), nullable=False),
        sa.Column("stay_id", sa.Integer(), sa.ForeignKey("stay.id"), nullable=True),
        sa.Column("channel", sa.String(), nullable=False, server_default="whatsapp"),
        sa.Column(
            "status",
            conversation_status,
            nullable=False,
            server_default=sa.text("'OPEN'::conversation_status"),
        ),
        sa.Column("current_handler", sa.String(), nullable=False, server_default="BOT"),
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
    op.create_index("ix_conversation_hotel_id", "conversation", ["hotel_id"])
    op.create_index("ix_conversation_guest_id", "conversation", ["guest_id"])
    op.create_index("ix_conversation_stay_id", "conversation", ["stay_id"])

    op.create_table(
        "message",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("conversation_id", sa.Integer(), sa.ForeignKey("conversation.id"), nullable=False),
        sa.Column("sender_type", message_sender, nullable=False),
        sa.Column("direction", message_direction, nullable=False),
        sa.Column("text", sa.Text(), nullable=False),
        sa.Column("raw_payload_json", postgresql.JSONB(), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("now()"),
        ),
    )
    op.create_index("ix_message_conversation_id", "message", ["conversation_id"])

    op.create_table(
        "task",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("hotel_id", sa.Integer(), sa.ForeignKey("hotel.id"), nullable=False),
        sa.Column("stay_id", sa.Integer(), sa.ForeignKey("stay.id"), nullable=True),
        sa.Column(
            "type",
            task_type,
            nullable=False,
            server_default=sa.text("'OTHER'::task_type"),
        ),
        sa.Column(
            "status",
            task_status,
            nullable=False,
            server_default=sa.text("'OPEN'::task_status"),
        ),
        sa.Column("payload_json", postgresql.JSONB(), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("now()"),
        ),
        sa.Column("completed_at", sa.DateTime(timezone=True), nullable=True),
    )
    op.create_index("ix_task_hotel_id", "task", ["hotel_id"])
    op.create_index("ix_task_stay_id", "task", ["stay_id"])

    op.create_table(
        "kb_article",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("hotel_id", sa.Integer(), sa.ForeignKey("hotel.id"), nullable=False),
        sa.Column("category", sa.String(), nullable=False),
        sa.Column("language", sa.String(), nullable=False, server_default="en"),
        sa.Column("title", sa.String(), nullable=False),
        sa.Column("body", sa.Text(), nullable=False),
        sa.Column("metadata_json", postgresql.JSONB(), nullable=True),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("now()"),
        ),
    )
    op.create_index("ix_kb_article_hotel_id", "kb_article", ["hotel_id"])

    op.create_table(
        "kb_embedding",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("kb_article_id", sa.Integer(), sa.ForeignKey("kb_article.id"), nullable=False),
        sa.Column("embedding", pgvector.sqlalchemy.Vector(1536)),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("now()"),
        ),
    )
    op.create_index("ix_kb_embedding_article_id", "kb_embedding", ["kb_article_id"])

    op.create_table(
        "staff_user",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("hotel_id", sa.Integer(), sa.ForeignKey("hotel.id"), nullable=False),
        sa.Column("name", sa.String(), nullable=False),
        sa.Column("role", sa.String(), nullable=False),
        sa.Column("email", sa.String(), nullable=False),
        sa.Column("password_hash", sa.String(), nullable=False),
        sa.Column("is_active", sa.Boolean(), nullable=False, server_default=sa.text("true")),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("now()"),
        ),
        sa.UniqueConstraint("email", name="uq_staff_user_email"),
    )
    op.create_index("ix_staff_user_hotel_id", "staff_user", ["hotel_id"])


def downgrade() -> None:
    op.drop_index("ix_staff_user_hotel_id", table_name="staff_user")
    op.drop_table("staff_user")

    op.drop_index("ix_kb_embedding_article_id", table_name="kb_embedding")
    op.drop_table("kb_embedding")

    op.drop_index("ix_kb_article_hotel_id", table_name="kb_article")
    op.drop_table("kb_article")

    op.drop_index("ix_task_stay_id", table_name="task")
    op.drop_index("ix_task_hotel_id", table_name="task")
    op.drop_table("task")

    op.drop_index("ix_message_conversation_id", table_name="message")
    op.drop_table("message")

    op.drop_index("ix_conversation_stay_id", table_name="conversation")
    op.drop_index("ix_conversation_guest_id", table_name="conversation")
    op.drop_index("ix_conversation_hotel_id", table_name="conversation")
    op.drop_table("conversation")

    op.drop_index("ix_stay_room_id", table_name="stay")
    op.drop_index("ix_stay_guest_id", table_name="stay")
    op.drop_index("ix_stay_hotel_id", table_name="stay")
    op.drop_table("stay")

    op.drop_index("ix_room_hotel_id", table_name="room")
    op.drop_table("room")

    op.drop_table("guest_pii")

    op.drop_index("ix_guest_hotel_id", table_name="guest")
    op.drop_table("guest")

    op.drop_table("hotel")

    sa.Enum(name="task_type").drop(op.get_bind(), checkfirst=True)
    sa.Enum(name="task_status").drop(op.get_bind(), checkfirst=True)
    sa.Enum(name="message_direction").drop(op.get_bind(), checkfirst=True)
    sa.Enum(name="message_sender").drop(op.get_bind(), checkfirst=True)
    sa.Enum(name="conversation_status").drop(op.get_bind(), checkfirst=True)
    sa.Enum(name="stay_status").drop(op.get_bind(), checkfirst=True)
