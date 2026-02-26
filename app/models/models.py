import enum

from pgvector.sqlalchemy import Vector
from sqlalchemy import JSON
from sqlalchemy import JSON as JSONType
from sqlalchemy import (
    Boolean,
    Column,
    DateTime,
    Enum,
    ForeignKey,
    Integer,
    String,
    Text,
    UniqueConstraint,
)
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func

from app.core.db import Base
from app.core.encrypted_type import EncryptedString


class StayStatus(str, enum.Enum):
    PRE_STAY = "PRE_STAY"
    IN_HOUSE = "IN_HOUSE"
    POST_STAY = "POST_STAY"
    CANCELLED = "CANCELLED"


class ConversationStatus(str, enum.Enum):
    OPEN = "OPEN"
    ASSIGNED_TO_STAFF = "ASSIGNED_TO_STAFF"
    CLOSED = "CLOSED"


class MessageSender(str, enum.Enum):
    GUEST = "GUEST"
    BOT = "BOT"
    STAFF = "STAFF"


class MessageDirection(str, enum.Enum):
    INCOMING = "INCOMING"
    OUTGOING = "OUTGOING"


class TaskStatus(str, enum.Enum):
    OPEN = "OPEN"
    IN_PROGRESS = "IN_PROGRESS"
    DONE = "DONE"
    CANCELLED = "CANCELLED"


class TaskType(str, enum.Enum):
    HOUSEKEEPING = "HOUSEKEEPING"
    MAINTENANCE = "MAINTENANCE"
    LOST_AND_FOUND = "LOST_AND_FOUND"
    FOOD_BEVERAGE = "FOOD_BEVERAGE"
    OTHER = "OTHER"


class TimestampMixin:
    created_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    updated_at = Column(
        DateTime(timezone=True),
        server_default=func.now(),
        onupdate=func.now(),
        nullable=False,
    )


class Hotel(Base, TimestampMixin):
    __tablename__ = "hotel"

    id = Column(Integer, primary_key=True)
    name = Column(String, nullable=False)
    timezone = Column(String, nullable=False, default="UTC")
    is_active = Column(Boolean, nullable=False, default=True)
    # Integrations (sensitive fields encrypted at rest)
    pms_type = Column(String, nullable=True)
    pms_api_key = Column(EncryptedString, nullable=True)  # ENCRYPTED
    pms_property_id = Column(String, nullable=True)
    whatsapp_phone_id = Column(String, nullable=True)
    whatsapp_business_account_id = Column(String, nullable=True)
    whatsapp_access_token = Column(EncryptedString, nullable=True)  # ENCRYPTED
    staff_language = Column(String(5), nullable=True)
    staff_alert_phone = Column(String, nullable=True)
    security_pin = Column(EncryptedString, nullable=True)  # ENCRYPTED
    interface_language = Column(String, nullable=False, default="en")
    language_locked = Column(Boolean, nullable=False, default=False)
    settings = Column(JSONType, nullable=True, default=dict)
    # Subscription fields
    country = Column(String(2), nullable=True)  # TH, RO, etc.
    subscription_tier = Column(String(20), nullable=False, default="free")  # free/basic/pro
    trial_ends_at = Column(DateTime(timezone=True), nullable=True)
    stripe_customer_id = Column(EncryptedString, nullable=True)  # ENCRYPTED
    stripe_subscription_id = Column(String, nullable=True)  # Stripe subscription ID

    guests = relationship("Guest", back_populates="hotel", cascade="all, delete-orphan")
    rooms = relationship("Room", back_populates="hotel", cascade="all, delete-orphan")
    stays = relationship("Stay", back_populates="hotel", cascade="all, delete-orphan")
    conversations = relationship(
        "Conversation", back_populates="hotel", cascade="all, delete-orphan"
    )
    tasks = relationship("Task", back_populates="hotel", cascade="all, delete-orphan")
    kb_articles = relationship("KBArticle", back_populates="hotel", cascade="all, delete-orphan")
    staff_users = relationship("StaffUser", back_populates="hotel", cascade="all, delete-orphan")
    ai_profile = relationship(
        "HotelAIProfile",
        back_populates="hotel",
        uselist=False,
        cascade="all, delete-orphan",
    )
    # Additional cascade relationships for complete hotel deletion
    journeys = relationship("Journey", back_populates="hotel", cascade="all, delete-orphan")
    journey_events = relationship(
        "JourneyEvent", back_populates="hotel", cascade="all, delete-orphan"
    )
    usage_events = relationship("UsageEvent", back_populates="hotel", cascade="all, delete-orphan")
    usage_daily = relationship("UsageDaily", back_populates="hotel", cascade="all, delete-orphan")


class Guest(Base):
    __tablename__ = "guest"
    __table_args__ = (
        UniqueConstraint("hotel_id", "phone_hash", name="uq_guest_hotel_phone"),
        UniqueConstraint("hotel_id", "line_user_id", name="uq_guest_hotel_line_user"),
    )

    id = Column(Integer, primary_key=True)
    hotel_id = Column(Integer, ForeignKey("hotel.id"), nullable=False, index=True)
    phone_hash = Column(String, nullable=False)
    line_user_id = Column(String, nullable=True, index=True)
    preferred_language = Column(String, nullable=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)

    hotel = relationship("Hotel", back_populates="guests")
    pii = relationship(
        "GuestPII", back_populates="guest", uselist=False, cascade="all, delete-orphan"
    )
    stays = relationship("Stay", back_populates="guest")
    conversations = relationship("Conversation", back_populates="guest")


class GuestPII(Base):
    __tablename__ = "guest_pii"

    guest_id = Column(Integer, ForeignKey("guest.id"), primary_key=True)
    full_name = Column(EncryptedString, nullable=True)
    phone_plain = Column(EncryptedString, nullable=True)
    email_plain = Column(EncryptedString, nullable=True)
    other_pii_json = Column(JSONB, nullable=True)

    guest = relationship("Guest", back_populates="pii")


class Room(Base):
    __tablename__ = "room"

    id = Column(Integer, primary_key=True)
    hotel_id = Column(Integer, ForeignKey("hotel.id"), nullable=False, index=True)
    room_number = Column(String, nullable=False)
    floor = Column(String, nullable=True)
    type = Column(String, nullable=True)
    is_active = Column(Boolean, nullable=False, default=True)

    hotel = relationship("Hotel", back_populates="rooms")
    stays = relationship("Stay", back_populates="room")
    conversations = relationship("Conversation", back_populates="room")  # BASIC tier


class Stay(Base, TimestampMixin):
    __tablename__ = "stay"

    id = Column(Integer, primary_key=True)
    hotel_id = Column(Integer, ForeignKey("hotel.id"), nullable=False, index=True)
    guest_id = Column(Integer, ForeignKey("guest.id"), nullable=False, index=True)
    room_id = Column(Integer, ForeignKey("room.id"), nullable=True, index=True)
    checkin_date = Column(DateTime(timezone=True), nullable=False)
    checkout_date = Column(DateTime(timezone=True), nullable=False)
    status = Column(
        Enum(StayStatus, name="stay_status"),
        nullable=False,
        default=StayStatus.PRE_STAY,
    )
    whatsapp_opt_in = Column(Boolean, nullable=False, default=True)
    channel = Column(String, nullable=True)
    pms_reservation_id = Column(String, nullable=True)

    hotel = relationship("Hotel", back_populates="stays")
    guest = relationship("Guest", back_populates="stays")
    room = relationship("Room", back_populates="stays")
    conversations = relationship("Conversation", back_populates="stay")
    tasks = relationship("Task", back_populates="stay")


class Conversation(Base, TimestampMixin):
    __tablename__ = "conversation"

    id = Column(Integer, primary_key=True)
    hotel_id = Column(Integer, ForeignKey("hotel.id"), nullable=False, index=True)
    guest_id = Column(Integer, ForeignKey("guest.id"), nullable=False, index=True)
    stay_id = Column(Integer, ForeignKey("stay.id"), nullable=True, index=True)
    room_id = Column(Integer, ForeignKey("room.id"), nullable=True, index=True)  # BASIC tier
    channel = Column(String, nullable=False, default="whatsapp")
    status = Column(
        Enum(ConversationStatus, name="conversation_status"),
        nullable=False,
        default=ConversationStatus.OPEN,
    )
    current_handler = Column(String, nullable=False, default="BOT")
    pending_confirmation = Column(Text, nullable=True)
    is_bot_paused = Column(Boolean, nullable=False, default=False)
    last_qr_scan_at = Column(DateTime(timezone=True), nullable=True)

    hotel = relationship("Hotel", back_populates="conversations")
    guest = relationship("Guest", back_populates="conversations")
    stay = relationship("Stay", back_populates="conversations")
    room = relationship("Room", back_populates="conversations")  # BASIC tier
    messages = relationship("Message", back_populates="conversation", cascade="all, delete-orphan")


class Message(Base):
    __tablename__ = "message"

    id = Column(Integer, primary_key=True)
    conversation_id = Column(Integer, ForeignKey("conversation.id"), nullable=False, index=True)
    sender_type = Column(Enum(MessageSender, name="message_sender"), nullable=False)
    direction = Column(Enum(MessageDirection, name="message_direction"), nullable=False)
    text = Column(Text, nullable=False)
    raw_payload_json = Column(JSONB, nullable=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)

    conversation = relationship("Conversation", back_populates="messages")


class Task(Base):
    __tablename__ = "task"

    id = Column(Integer, primary_key=True)
    hotel_id = Column(Integer, ForeignKey("hotel.id"), nullable=False, index=True)
    stay_id = Column(Integer, ForeignKey("stay.id"), nullable=True, index=True)
    type = Column(Enum(TaskType, name="task_type"), nullable=False, default=TaskType.OTHER)
    status = Column(Enum(TaskStatus, name="task_status"), nullable=False, default=TaskStatus.OPEN)
    payload_json = Column(JSONB, nullable=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    completed_at = Column(DateTime(timezone=True), nullable=True)
    staff_summary = Column(Text, nullable=True)
    priority = Column(String, nullable=False, default="NORMAL")

    hotel = relationship("Hotel", back_populates="tasks")
    stay = relationship("Stay", back_populates="tasks")


class KBArticle(Base):
    __tablename__ = "kb_article"

    id = Column(Integer, primary_key=True)
    hotel_id = Column(Integer, ForeignKey("hotel.id"), nullable=False, index=True)
    category = Column(String, nullable=False)
    language = Column(String, nullable=False, default="en")
    title = Column(String, nullable=False)
    body = Column(Text, nullable=False)
    metadata_json = Column(JSON, nullable=True)
    updated_at = Column(
        DateTime(timezone=True),
        server_default=func.now(),
        onupdate=func.now(),
        nullable=False,
    )

    hotel = relationship("Hotel", back_populates="kb_articles")
    embeddings = relationship(
        "KBEmbedding", back_populates="kb_article", cascade="all, delete-orphan"
    )


class KBEmbedding(Base):
    __tablename__ = "kb_embedding"

    id = Column(Integer, primary_key=True)
    kb_article_id = Column(Integer, ForeignKey("kb_article.id"), nullable=False, index=True)
    embedding = Column(Vector(1536))
    created_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)

    kb_article = relationship("KBArticle", back_populates="embeddings")


class StaffUser(Base):
    __tablename__ = "staff_user"

    id = Column(Integer, primary_key=True)
    hotel_id = Column(Integer, ForeignKey("hotel.id"), nullable=False, index=True)
    name = Column(String, nullable=False)
    role = Column(String, nullable=False)
    email = Column(String, nullable=False, unique=True)
    password_hash = Column(String, nullable=False)
    is_active = Column(Boolean, nullable=False, default=True)
    must_change_password = Column(Boolean, nullable=False, default=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)

    hotel = relationship("Hotel", back_populates="staff_users")


class PlatformOwner(Base):
    __tablename__ = "platform_owner"

    id = Column(Integer, primary_key=True)
    email = Column(String, nullable=False, unique=True)
    password_hash = Column(String, nullable=False)
    is_active = Column(Boolean, nullable=False, default=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)


class PasswordResetToken(Base):
    __tablename__ = "password_reset_token"

    id = Column(Integer, primary_key=True)
    user_type = Column(String, nullable=False)  # 'staff' or 'owner'
    user_id = Column(Integer, nullable=False)
    token = Column(String, nullable=False, unique=True, index=True)
    expires_at = Column(DateTime(timezone=True), nullable=False)
    created_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)


class SystemSetting(Base, TimestampMixin):
    __tablename__ = "system_setting"
    __table_args__ = (UniqueConstraint("key", name="uq_system_setting_key"),)

    id = Column(Integer, primary_key=True)
    key = Column(String, nullable=False)
    value = Column(Text, nullable=True)


class HotelAIProfile(Base):
    __tablename__ = "hotel_ai_profile"

    id = Column(Integer, primary_key=True)
    hotel_id = Column(Integer, ForeignKey("hotel.id"), nullable=False, unique=True, index=True)
    bot_name = Column(String, nullable=True)
    tone = Column(String, nullable=True)
    use_emojis = Column(Boolean, nullable=False, default=True)
    max_reply_sentences = Column(Integer, nullable=False, default=2)
    primary_language = Column(String(5), nullable=True)
    reply_in_guest_language = Column(Boolean, nullable=False, default=True)
    wifi_ssid = Column(String, nullable=True)
    wifi_password = Column(EncryptedString, nullable=True)  # ENCRYPTED
    breakfast_hours = Column(Text, nullable=True)
    parking_info = Column(Text, nullable=True)
    late_checkout_policy = Column(Text, nullable=True)
    custom_instructions = Column(Text, nullable=True)

    hotel = relationship("Hotel", back_populates="ai_profile")


class Journey(Base, TimestampMixin):
    __tablename__ = "journey"

    id = Column(Integer, primary_key=True)
    hotel_id = Column(Integer, ForeignKey("hotel.id"), nullable=False, index=True)
    name = Column(String, nullable=False)
    type = Column(String, nullable=False)
    delay_minutes = Column(Integer, nullable=False, default=20)
    is_active = Column(Boolean, nullable=False, default=True)
    template_key = Column(String, nullable=False)

    hotel = relationship("Hotel", back_populates="journeys")
    events = relationship("JourneyEvent", back_populates="journey", cascade="all, delete-orphan")


class JourneyEventStatus(str, enum.Enum):
    PENDING = "PENDING"
    SENT = "SENT"
    CANCELLED = "CANCELLED"


class JourneyEvent(Base, TimestampMixin):
    __tablename__ = "journey_event"

    id = Column(Integer, primary_key=True)
    hotel_id = Column(Integer, ForeignKey("hotel.id"), nullable=False, index=True)
    journey_id = Column(Integer, ForeignKey("journey.id"), nullable=False, index=True)
    guest_id = Column(Integer, ForeignKey("guest.id"), nullable=False, index=True)
    stay_id = Column(Integer, ForeignKey("stay.id"), nullable=False, index=True)
    channel = Column(String, nullable=False, default="whatsapp")
    run_at = Column(DateTime(timezone=True), nullable=False)
    status = Column(
        Enum(JourneyEventStatus, name="journey_event_status"),
        nullable=False,
        default=JourneyEventStatus.PENDING,
    )

    hotel = relationship("Hotel", back_populates="journey_events")
    journey = relationship("Journey", back_populates="events")
    guest = relationship("Guest")
    stay = relationship("Stay")


class UsageEvent(Base):
    __tablename__ = "usage_event"

    id = Column(Integer, primary_key=True)
    hotel_id = Column(Integer, ForeignKey("hotel.id"), nullable=False, index=True)
    event_type = Column(String, nullable=False)
    value_int = Column(Integer, nullable=False, default=1)
    metadata_json = Column(JSONB, nullable=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)

    hotel = relationship("Hotel", back_populates="usage_events")


class UsageDaily(Base, TimestampMixin):
    __tablename__ = "usage_daily"
    __table_args__ = (UniqueConstraint("hotel_id", "date", name="uq_usage_daily_hotel_date"),)

    id = Column(Integer, primary_key=True)
    hotel_id = Column(Integer, ForeignKey("hotel.id"), nullable=False, index=True)
    date = Column(DateTime(timezone=False), nullable=False)
    messages_in = Column(Integer, nullable=False, default=0)
    messages_out_bot = Column(Integer, nullable=False, default=0)
    messages_out_staff = Column(Integer, nullable=False, default=0)
    tasks_created = Column(Integer, nullable=False, default=0)
    tasks_done = Column(Integer, nullable=False, default=0)
    llm_calls = Column(Integer, nullable=False, default=0)
    llm_tokens = Column(Integer, nullable=False, default=0)

    hotel = relationship("Hotel", back_populates="usage_daily")


class StripeWebhookEvent(Base):
    """Track processed Stripe webhook events for idempotency."""

    __tablename__ = "stripe_webhook_event"

    id = Column(Integer, primary_key=True)
    event_id = Column(String, nullable=False, unique=True, index=True)  # Stripe event ID
    event_type = Column(String, nullable=False)
    processed_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)
