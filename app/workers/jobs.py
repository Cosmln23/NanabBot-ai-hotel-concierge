"""
Background jobs for message processing.
Clean and simple - uses brain.py for all LLM processing.
"""

import logging
import re
from datetime import datetime, timedelta, timezone
from typing import Optional

from sqlalchemy.orm import Session

from app.agent.brain import process_with_brain
from app.core.db import SessionLocal
from app.models import (
    Conversation,
    ConversationStatus,
    Guest,
    Hotel,
    Message,
    MessageDirection,
    MessageSender,
    Room,
    Stay,
    StayStatus,
)
from app.services.analytics import log_message_out_bot
from app.services.messaging.factory import get_message_provider
from app.services.messaging.providers.line import LineProvider
from app.services.whatsapp_client import get_welcome_buttons, send_interactive_message
from app.workers.queue import redis_conn

logger = logging.getLogger(__name__)

# Bilingual prompt for LINE room linking
BILINGUAL_PROMPT = (
    "Welcome! To connect, please reply with your Room Number.\n"
    "เพื่อเริ่มใช้งาน กรุณาพิมพ์ หมายเลขห้องพัก ของคุณ"
)

# Default welcome messages by language and tone (BASIC tier - no guest name)
PROFESSIONAL_WELCOME = {
    "en": "Good day, I'm {bot_name}, the virtual assistant of {hotel_name}. You are connected to room {room}. I can assist you with: WiFi information, breakfast schedule, check-in/check-out times, parking, housekeeping, or other requests. How may I be of service?",
}

FRIENDLY_WELCOME = {
    "en": "Hey! 👋 I'm {bot_name} from {hotel_name}! You're in room {room}. I can help with WiFi, breakfast, parking, housekeeping and more! 😊 What can I help you with?",
}

# PRO tier welcome messages with {guest_name} from PMS
PROFESSIONAL_WELCOME_PRO = {
    "en": "Good day {guest_name}, I'm {bot_name}, the virtual assistant of {hotel_name}. You are in room {room}. I can assist you with: WiFi information, breakfast schedule, check-in/check-out times, parking, housekeeping, or other requests. How may I be of service?",
}

FRIENDLY_WELCOME_PRO = {
    "en": "Hey {guest_name}! 👋 I'm {bot_name} from {hotel_name}! You're in room {room}. I can help with WiFi, breakfast, parking, housekeeping and more! 😊 What can I help you with?",
}

# English follow-up message for bilingual welcome (tourists)
ENGLISH_FOLLOWUP = {
    "professional": "Hi {guest_name}! I'm {bot_name} from {hotel_name}. You're in room {room}. I can help with WiFi, breakfast, check-in/out, parking, housekeeping and more. I can assist you in any language! 🌍",
    "friendly": "Hi {guest_name}! 👋 I'm {bot_name} from {hotel_name}! Room {room}. I can help with WiFi, breakfast, parking, housekeeping & more! I speak any language! 🌍😊",
}

# Session expired messages (BASIC tier - no AI cost, system-level message)
SESSION_EXPIRED_MESSAGES = {
    "en": "Chat session expired for security reasons. Please scan the room QR code again to continue.",
}

# Stay ended messages (PRO tier - guest checked out, system-level message)
STAY_ENDED_MESSAGES = {
    "en": "Your stay has ended. Thank you for being our guest! For a new reservation, please contact reception.",
}


def _get_welcome_message(hotel: Hotel, room_number: str, guest_name: str = None) -> str:
    """Get welcome message based on tone setting.

    Args:
        hotel: Hotel object
        room_number: Room number string
        guest_name: Guest name for PRO tier (from PMS). If provided, uses PRO templates.

    Returns:
        Welcome message string
    """
    # Bot name is always AI Hotel Suite (hardcoded for branding)
    bot_name = "AI Hotel Suite"
    hotel_name = hotel.name or "hotel"

    # Get tone (default: professional)
    tone = "professional"
    if hotel.ai_profile and hotel.ai_profile.tone:
        tone = hotel.ai_profile.tone

    # Select template based on tone and PRO/BASIC tier
    lang = hotel.staff_language or hotel.interface_language or "en"

    if guest_name:
        # PRO tier - use templates with guest name
        if tone == "friendly":
            templates = FRIENDLY_WELCOME_PRO
        else:
            templates = PROFESSIONAL_WELCOME_PRO
        template = templates.get(lang, templates["en"])
        return template.format(
            bot_name=bot_name,
            hotel_name=hotel_name,
            room=room_number,
            guest_name=guest_name,
        )
    else:
        # BASIC tier - no guest name
        if tone == "friendly":
            templates = FRIENDLY_WELCOME
        else:
            templates = PROFESSIONAL_WELCOME
        template = templates.get(lang, templates["en"])
        return template.format(bot_name=bot_name, hotel_name=hotel_name, room=room_number)


def _get_english_followup(hotel: Hotel, room_number: str, guest_name: str = None) -> str:
    """Get English follow-up message for bilingual welcome option.

    Args:
        hotel: Hotel object
        room_number: Room number string
        guest_name: Guest name (optional)

    Returns:
        English follow-up message
    """
    # Bot name is always AI Hotel Suite (hardcoded for branding)
    bot_name = "AI Hotel Suite"
    hotel_name = hotel.name or "hotel"

    tone = "professional"
    if hotel.ai_profile and hotel.ai_profile.tone:
        tone = hotel.ai_profile.tone

    template = ENGLISH_FOLLOWUP.get(tone, ENGLISH_FOLLOWUP["professional"])
    return template.format(
        bot_name=bot_name,
        hotel_name=hotel_name,
        room=room_number,
        guest_name=guest_name or "Guest",
    )


def _extract_recipient_id(message: Message) -> Optional[str]:
    """Extract WhatsApp/LINE user ID from message payload."""
    payload = message.raw_payload_json or {}
    if isinstance(payload, dict):
        # LINE
        if payload.get("line_user_id"):
            return payload.get("line_user_id")
        source = payload.get("source") or {}
        if source.get("userId"):
            return source.get("userId")
        # WhatsApp
        contacts = payload.get("contacts", [])
        if contacts:
            wa_id = contacts[0].get("wa_id")
            if wa_id:
                return wa_id
        if "from" in payload:
            return payload.get("from")
    return None


def _send_line_welcome_with_buttons(provider, line_user_id: str, welcome_msg: str, hotel) -> None:
    """Send LINE welcome message with Quick Reply buttons (fallback to plain text)."""
    buttons = get_welcome_buttons(hotel)
    if isinstance(provider, LineProvider) and buttons:
        success = provider.send_quick_reply_message(
            user_id=line_user_id, text=welcome_msg, buttons=buttons
        )
        if not success:
            provider.send_text(phone_number=line_user_id, message=welcome_msg)
    else:
        provider.send_text(phone_number=line_user_id, message=welcome_msg)


def _handle_line_room_linking(
    db: Session, conversation: Conversation, message: Message, line_user_id: str
) -> bool:
    """
    Handle room-number linking flow for unlinked LINE users.
    Returns True if handled (and we should stop further processing).
    Allows room changes when user scans a new QR code (BASIC tier).
    PRO tier uses PMS Stay for room, so line_user_id check blocks re-linking.
    """
    guest = conversation.guest

    # PRO tier: If guest already linked via line_user_id, room comes from PMS Stay
    if guest and guest.line_user_id:
        return False  # PRO tier - room managed by PMS

    provider = get_message_provider(conversation.hotel)
    text = (message.text or "").strip()
    redis_key = f"pending_link:{line_user_id}"

    # Check if this is a QR code scan (allows room change for BASIC tier)
    is_qr_scan = False
    # Bilingual format: "เชื่อมต่อห้อง X / Connect Room X"
    bilingual_match = re.match(r"^เชื่อมต่อห้อง\s+(\d+)\s*/\s*connect\s+room\s+\d+$", text.lower())
    if bilingual_match:
        is_qr_scan = True
    else:
        # Single language QR formats
        qr_match = re.match(
            r"^(?:connect\s+room|conecteaz[aă]\s+camera|เชื่อมต่อห้อง|int_room_qr_connect)\s+(\d+)(?:\s+#(\d+))?$",
            text.lower(),
        )
        if qr_match:
            is_qr_scan = True

    # BASIC tier: If room already linked and NOT a QR scan, skip
    if conversation.room_id and not is_qr_scan:
        return False  # Already linked, only QR scan can change room

    # Confirmation path - accept YES (English) and ใช่ (Thai)
    if text.lower() in ("yes", "ใช่"):
        pending_guest_id = redis_conn.get(redis_key)
        if pending_guest_id:
            try:
                pending_guest_id = int(pending_guest_id)
            except Exception:
                redis_conn.delete(redis_key)
                return True
            target_guest = db.query(Guest).filter(Guest.id == pending_guest_id).first()
            if target_guest:
                target_guest.line_user_id = line_user_id
                conversation.guest_id = target_guest.id
                db.add(target_guest)
                db.add(conversation)
                db.commit()
                redis_conn.delete(redis_key)

                # PRO tier welcome - use guest name from PMS
                hotel = conversation.hotel
                settings = hotel.settings or {} if hotel else {}

                # Get room number and guest name from stay
                stay = (
                    db.query(Stay)
                    .filter(
                        Stay.guest_id == target_guest.id,
                        Stay.status == StayStatus.IN_HOUSE,
                    )
                    .first()
                )
                room_num = stay.room.room_number if stay and stay.room else ""
                guest_name = None
                if target_guest.pii and target_guest.pii.full_name:
                    guest_name = target_guest.pii.full_name

                # Send main welcome with "Connected!" prefix + Quick Reply buttons
                welcome_msg = _get_welcome_message(hotel, room_num, guest_name=guest_name)

                if settings.get("bilingual_welcome", False):
                    # Bilingual: buttons on LAST message so they don't disappear
                    provider.send_text(
                        phone_number=line_user_id, message=f"Connected! 🎉\n{welcome_msg}"
                    )
                    welcome_english = _get_english_followup(hotel, room_num, guest_name=guest_name)
                    _send_line_welcome_with_buttons(provider, line_user_id, welcome_english, hotel)
                else:
                    _send_line_welcome_with_buttons(
                        provider, line_user_id, f"Connected! 🎉\n{welcome_msg}", hotel
                    )

                return True

    # Room number path (BASIC tier linking)
    # Support direct room numbers ("101") and QR format ("Connect Room 101")
    # NOTE: LINE uses dedicated channels per hotel, so #hotel_id suffix is NOT needed
    # Multi-tenant routing code below is DISABLED (kept for monitoring - delete if no issues after testing)
    room_number = None
    # DISABLED: extracted_hotel_id = None  # LINE doesn't need multi-tenant routing

    # BASIC tier: Only accept QR format, NOT plain room numbers
    # This prevents reconnection without scanning QR after session expires
    # - English: "Connect Room X"
    match = re.match(
        r"^(?:connect\s+room)\s+(\d+)$",
        text.lower(),
    )
    if match:
        room_number = match.group(1)

    if room_number:
        # DISABLED multi-tenant routing - LINE always uses conversation.hotel_id
        # target_hotel_id = int(extracted_hotel_id) if extracted_hotel_id else conversation.hotel_id
        # if extracted_hotel_id and int(extracted_hotel_id) != conversation.hotel_id:
        #     logger.info(f"QR routing: message routed to hotel {extracted_hotel_id} (from QR code) instead of {conversation.hotel_id}")

        # Try to find a stay with this room (PRO tier)
        stay = (
            db.query(Stay)
            .join(Room, Stay.room_id == Room.id)
            .filter(
                Stay.status == StayStatus.IN_HOUSE,
                Room.room_number == room_number,
                Stay.hotel_id == conversation.hotel_id,  # LINE: use conversation's hotel
            )
            .order_by(Stay.checkin_date.desc())
            .first()
        )

        if stay:
            # PRO tier - link to stay
            redis_conn.setex(redis_key, 300, stay.guest_id)
            guest_name = "Guest"
            if stay.guest and stay.guest.pii:
                guest_name = stay.guest.pii.full_name or "Guest"

            confirm = f"Are you {guest_name}? (Reply YES)"
            provider.send_text(phone_number=line_user_id, message=confirm)
            return True
        else:
            # BASIC/FREE tier - find or create room, then link
            room = (
                db.query(Room)
                .filter(
                    Room.hotel_id == conversation.hotel_id,
                    Room.room_number == room_number,
                )  # LINE: use conversation's hotel
                .first()
            )
            if not room:
                # Auto-create room for BASIC/FREE tier
                room = Room(
                    hotel_id=conversation.hotel_id, room_number=room_number
                )  # LINE: use conversation's hotel
                db.add(room)
                db.commit()
                db.refresh(room)
                logger.info(
                    f"Auto-created Room {room_number} for hotel {conversation.hotel_id} (LINE)"
                )

            conversation.room_id = room.id
            conversation.last_qr_scan_at = datetime.now(timezone.utc)  # Session start
            db.add(conversation)
            db.commit()

            # Send welcome message with Quick Reply buttons
            hotel = conversation.hotel
            welcome_msg = _get_welcome_message(hotel, room_number)
            settings = hotel.settings or {}

            if settings.get("bilingual_welcome", False):
                # Bilingual: buttons on LAST message so they don't disappear
                provider.send_text(phone_number=line_user_id, message=welcome_msg)
                welcome_english = _get_english_followup(hotel, room_number)
                _send_line_welcome_with_buttons(provider, line_user_id, welcome_english, hotel)
            else:
                _send_line_welcome_with_buttons(provider, line_user_id, welcome_msg, hotel)

            return True

    # Unlinked user must scan QR - don't accept plain room numbers
    hotel = conversation.hotel
    settings = hotel.settings or {} if hotel else {}
    lang = hotel.staff_language or hotel.interface_language or "en" if hotel else "en"
    scan_qr_msg = SESSION_EXPIRED_MESSAGES.get(lang, SESSION_EXPIRED_MESSAGES["en"])
    provider.send_text(phone_number=line_user_id, message=scan_qr_msg)

    # Bilingual: send English follow-up if enabled and primary language is not English
    if settings.get("bilingual_welcome", False) and lang != "en":
        provider.send_text(phone_number=line_user_id, message=SESSION_EXPIRED_MESSAGES["en"])

    return True


def _handle_whatsapp_room_linking(
    db: Session, conversation: Conversation, message: Message, wa_id: str
) -> bool:
    """
    Handle room-number linking flow for WhatsApp users (BASIC/FREE tier).
    Returns True if handled (and we should stop further processing).
    Allows room changes when user scans a new QR code (physical presence).
    """
    hotel = conversation.hotel
    if not hotel:
        return False

    # Only for BASIC/FREE tier (PRO tier uses PMS for stay linking)
    tier = getattr(hotel, "subscription_tier", "free")
    if tier == "pro":
        return False

    provider = get_message_provider(hotel)
    text = (message.text or "").strip()

    # Parse room number from QR code formats or just "X"
    # NOTE: WhatsApp uses shared number across hotels, so #hotel_id suffix IS needed for multi-tenant routing
    room_number = None
    extracted_hotel_id = None  # WhatsApp NEEDS multi-tenant routing
    extracted_token = None  # QR token for anti-spoofing
    is_qr_scan = False  # Track if this is a physical QR code scan

    # Single language: EN
    # WhatsApp multi-tenant: capture optional #hotel_id and !token suffix
    # Use case-insensitive flag so token (hex, lowercase) is preserved correctly
    match = re.match(
        r"^(?:connect\s+room)\s+(\d+)(?:\s+#(\d+))?(?:\s+!([a-f0-9]+))?$",
        text,
        re.IGNORECASE,
    )
    if match:
        room_number = match.group(1)
        extracted_hotel_id = match.group(2)  # Extract #hotel_id from QR code
        extracted_token = match.group(3)  # Extract !token from QR code
        is_qr_scan = True
    elif text.isdigit() and 1 <= len(text) <= 4:
        # Plain room number (typed manually) - only if not already linked
        room_number = text

    # If no room number detected
    if not room_number:
        # No room linked → tell guest to scan QR (same guard as LINE)
        if not conversation.room_id:
            h_settings = hotel.settings or {}
            lang = hotel.staff_language or hotel.interface_language or "en"
            scan_qr_msg = SESSION_EXPIRED_MESSAGES.get(lang, SESSION_EXPIRED_MESSAGES["en"])
            provider.send_text(phone_number=wa_id, message=scan_qr_msg)
            if h_settings.get("bilingual_welcome", False) and lang != "en":
                provider.send_text(phone_number=wa_id, message=SESSION_EXPIRED_MESSAGES["en"])
            return True
        return False

    # Security: Plain typed numbers cannot change room (only QR scans can)
    if not is_qr_scan and conversation.room_id:
        return False

    # Validate QR token if hotel has tokens configured (anti-spoofing)
    if is_qr_scan and room_number:
        h_settings = hotel.settings or {}
        qr_tokens = h_settings.get("qr_tokens", {})
        if qr_tokens:
            # Hotel has QR tokens → token is required
            if not extracted_token or extracted_token not in qr_tokens:
                logger.warning(
                    f"QR token validation failed: token='{extracted_token}' for hotel {hotel.id}"
                )
                provider = get_message_provider(hotel)
                provider.send_text(
                    phone_number=wa_id,
                    message="This QR code is not valid. Please scan the QR code in your room.",
                )
                return True  # Handled (rejected)

    if room_number:
        # WhatsApp multi-tenant routing - use extracted hotel_id from QR code if present
        target_hotel_id = int(extracted_hotel_id) if extracted_hotel_id else conversation.hotel_id
        if extracted_hotel_id and int(extracted_hotel_id) != conversation.hotel_id:
            logger.info(
                f"QR routing: WhatsApp message routed to hotel {extracted_hotel_id} (from QR code) instead of {conversation.hotel_id}"
            )

        # Find or create room
        room = (
            db.query(Room)
            .filter(
                Room.hotel_id == target_hotel_id, Room.room_number == room_number
            )  # WhatsApp: use QR hotel
            .first()
        )
        if not room:
            # Auto-create room for BASIC/FREE tier
            room = Room(hotel_id=target_hotel_id, room_number=room_number)  # WhatsApp: use QR hotel
            db.add(room)
            db.commit()
            db.refresh(room)
            logger.info(
                f"Auto-created Room {room_number} for hotel {target_hotel_id} (WhatsApp multi-tenant)"
            )

        conversation.room_id = room.id
        conversation.last_qr_scan_at = datetime.now(timezone.utc)  # Session start
        db.add(conversation)
        db.commit()

        # Send welcome message with interactive buttons (WhatsApp only)
        welcome = _get_welcome_message(hotel, room_number)
        buttons = get_welcome_buttons(hotel)

        # Try to send interactive message with buttons
        success = send_interactive_message(
            wa_id=wa_id, body_text=welcome, buttons=buttons, hotel=hotel
        )

        # Fallback to plain text if interactive fails
        if not success:
            logger.warning(f"Interactive message failed for {wa_id}, falling back to text")
            provider.send_text(phone_number=wa_id, message=welcome)

        return True

    return False


def process_incoming_message(message_id: int) -> None:
    """
    Background job: Process incoming message with brain.py
    """
    db: Session = SessionLocal()
    try:
        message = db.query(Message).filter(Message.id == message_id).first()
        if not message:
            logger.warning(f"Message {message_id} not found")
            return

        conversation = (
            db.query(Conversation).filter(Conversation.id == message.conversation_id).first()
        )
        if not conversation:
            logger.warning(f"Conversation for message {message_id} not found")
            return

        # Check if bot is paused
        if getattr(conversation, "is_bot_paused", False):
            logger.info(f"Bot paused for conversation {conversation.id}")
            return

        # Check if hotel is active (subscription valid)
        hotel = conversation.hotel
        if hotel and not hotel.is_active:
            logger.info(f"Hotel {hotel.id} is not active, skipping message")
            return

        # Check if trial expired (FREE tier only)
        if hotel and hotel.subscription_tier == "free" and hotel.trial_ends_at:
            trial_ends = hotel.trial_ends_at
            if trial_ends.tzinfo is None:
                trial_ends = trial_ends.replace(tzinfo=timezone.utc)
            if datetime.now(timezone.utc) > trial_ends:
                logger.info(f"Trial expired for hotel {hotel.id} - message not processed")
                return  # Silent - guest receives nothing

        # LINE room-linking flow
        payload = message.raw_payload_json or {}
        line_user_id = None
        if isinstance(payload, dict):
            line_user_id = payload.get("line_user_id") or (payload.get("source") or {}).get(
                "userId"
            )

        if line_user_id:
            handled = _handle_line_room_linking(db, conversation, message, line_user_id)
            if handled:
                return

        # WhatsApp room-linking flow (BASIC/FREE tier)
        wa_id = _extract_recipient_id(message)
        if wa_id and not line_user_id:
            handled = _handle_whatsapp_room_linking(db, conversation, message, wa_id)
            if handled:
                return

        # === SESSION EXPIRY CHECK (BASIC tier) ===
        hotel = conversation.hotel
        settings = hotel.settings or {} if hotel else {}
        recipient_id = _extract_recipient_id(message)

        # Only check if qr_session_expiry is ENABLED in settings
        if settings.get("qr_session_expiry_enabled", True):
            # BASIC/FREE tier only (has room_id but no stay_id)
            if not conversation.stay_id and conversation.room_id:
                session_hours = settings.get("qr_session_hours", 48)
                last_scan = conversation.last_qr_scan_at

                if (
                    not last_scan
                    or (datetime.now(timezone.utc) - last_scan).total_seconds()
                    > session_hours * 3600
                ):
                    # SESSION EXPIRED - send system message, don't call AI
                    lang = hotel.staff_language or hotel.interface_language or "en"
                    expired_msg = SESSION_EXPIRED_MESSAGES.get(lang, SESSION_EXPIRED_MESSAGES["en"])

                    # Save system message to database for tracking
                    system_msg = Message(
                        conversation_id=conversation.id,
                        sender_type=MessageSender.BOT,
                        direction=MessageDirection.OUTGOING,
                        text=expired_msg,
                    )
                    db.add(system_msg)
                    db.commit()

                    if recipient_id and hotel:
                        try:
                            provider = get_message_provider(hotel)
                            provider.send_text(phone_number=recipient_id, message=expired_msg)

                            # Bilingual: send English follow-up if enabled and primary language is not English
                            if settings.get("bilingual_welcome", False) and lang != "en":
                                expired_msg_en = SESSION_EXPIRED_MESSAGES["en"]
                                provider.send_text(
                                    phone_number=recipient_id, message=expired_msg_en
                                )
                        except Exception as e:
                            logger.error(f"Failed to send session expired message: {e}")

                    # Close conversation so user must scan QR to create new one
                    conversation.room_id = None
                    conversation.status = ConversationStatus.CLOSED
                    db.add(conversation)
                    db.commit()
                    logger.info(
                        f"Session expired - conversation {conversation.id} closed (user must scan QR)"
                    )
                    return

        # === PRO TIER: Check Stay status ===
        if conversation.stay_id:
            stay = conversation.stay
            if stay and stay.status == StayStatus.POST_STAY:
                # Stay ended - send system message
                lang = hotel.staff_language or hotel.interface_language or "en" if hotel else "en"
                ended_msg = STAY_ENDED_MESSAGES.get(lang, STAY_ENDED_MESSAGES["en"])

                # Save system message to database for tracking
                system_msg = Message(
                    conversation_id=conversation.id,
                    sender_type=MessageSender.BOT,
                    direction=MessageDirection.OUTGOING,
                    text=ended_msg,
                )
                db.add(system_msg)
                db.commit()

                if recipient_id and hotel:
                    try:
                        provider = get_message_provider(hotel)
                        provider.send_text(phone_number=recipient_id, message=ended_msg)
                    except Exception as e:
                        logger.error(f"Failed to send stay ended message: {e}")

                logger.info(f"Stay ended for conversation {conversation.id} (stay {stay.id})")
                return  # STOP - don't process with AI

        # Process with brain (only if session valid)
        logger.info(f"Processing message {message_id} with brain...")
        bot_message = process_with_brain(db, message)

        if not bot_message:
            logger.error(f"Brain returned no response for message {message_id}")
            # Fallback: trimite mesaj generic la user
            try:
                recipient_id = _extract_recipient_id(message)
                if recipient_id and conversation.hotel:
                    provider = get_message_provider(conversation.hotel)
                    fallback = "Sorry, I encountered a problem. Please try again."
                    provider.send_text(phone_number=recipient_id, message=fallback)
            except Exception as e:
                logger.error(f"Failed to send fallback message: {e}")
            return

        # Log analytics
        try:
            log_message_out_bot(
                db,
                hotel_id=conversation.hotel_id,
                metadata={"conversation_id": conversation.id},
            )
        except Exception as e:
            logger.warning(f"Failed to log analytics: {e}")

        # Send response
        recipient_id = _extract_recipient_id(message)
        if bot_message.text and recipient_id:
            try:
                provider = get_message_provider(conversation.hotel)
                success = provider.send_text(phone_number=recipient_id, message=bot_message.text)
                if not success:
                    logger.error(f"Failed to send message to {recipient_id}")
            except Exception as e:
                logger.error(f"Error sending message: {e}")

    except Exception as e:
        logger.exception(f"Error processing message {message_id}: {e}")
    finally:
        db.close()


def aggregate_daily_usage(days_back: int = 2) -> None:
    """Aggregate daily analytics."""
    from app.services import analytics

    db: Session = SessionLocal()
    try:
        today = datetime.now(timezone.utc).date()
        for i in range(days_back):
            target_date = today - timedelta(days=i)
            analytics.aggregate_daily(db, target_date=target_date)
    except Exception as e:
        logger.exception(f"aggregate_daily_usage failed: {e}")
    finally:
        db.close()
