from datetime import datetime, timedelta, timezone

from sqlalchemy.orm import Session

from app.core.db import SessionLocal
from app.core.logging import logger
from app.models import (
    Conversation,
    ConversationStatus,
    Hotel,
    JourneyEvent,
    JourneyEventStatus,
    Message,
    MessageDirection,
    MessageSender,
    StayStatus,
)
from app.services.identity_resolver import determine_state
from app.services.journey_templates import TEMPLATES
from app.services.messaging.factory import get_message_provider
from app.services.whatsapp_client import send_template_message
from app.workers.jobs import _get_english_followup, _get_welcome_message


def _get_template_text(template_key: str, language: str) -> str:
    template = TEMPLATES.get(template_key) or {}
    return template.get(language) or template.get("en") or "Welcome!"


def _get_wa_id(event: JourneyEvent) -> str | None:
    pii = event.guest.pii if event.guest else None
    return pii.phone_plain if pii else None


def process_pending_journeys() -> None:
    db: Session = SessionLocal()
    try:
        now = datetime.now(timezone.utc)

        # 1. TIMEOUT: Cancel stale events (PENDING > 30 minutes)
        stale_cutoff = now - timedelta(minutes=30)
        stale_events = (
            db.query(JourneyEvent)
            .filter(
                JourneyEvent.status == JourneyEventStatus.PENDING,
                JourneyEvent.run_at <= stale_cutoff,
            )
            .all()
        )
        for stale in stale_events:
            stale.status = JourneyEventStatus.CANCELLED
            db.add(stale)
            logger.info(f"Cancelled stale journey event {stale.id} (pending > 30 min)")
        if stale_events:
            db.commit()

        # 2. Process fresh pending events
        events = (
            db.query(JourneyEvent)
            .filter(
                JourneyEvent.status == JourneyEventStatus.PENDING,
                JourneyEvent.run_at <= now,
            )
            .all()
        )
        logger.info(f"Found {len(events)} pending journey events to process")
        for event in events:
            logger.info(f"Processing event {event.id} for stay {event.stay_id}")
            stay = event.stay
            if not stay:
                event.status = JourneyEventStatus.CANCELLED
                db.add(event)
                db.commit()
                continue

            state = determine_state(stay)
            if state != StayStatus.IN_HOUSE:
                # keep pending to retry later until checkout passes; simple policy
                continue

            if stay.whatsapp_opt_in is False:
                event.status = JourneyEventStatus.CANCELLED
                db.add(event)
                db.commit()
                continue

            wa_id = _get_wa_id(event)
            if not wa_id:
                event.status = JourneyEventStatus.CANCELLED
                db.add(event)
                db.commit()
                continue

            conversation = (
                db.query(Conversation)
                .filter(
                    Conversation.hotel_id == event.hotel_id,
                    Conversation.guest_id == event.guest_id,
                    Conversation.channel == "whatsapp",
                    Conversation.status == ConversationStatus.OPEN,
                )
                .order_by(Conversation.created_at.desc())
                .first()
            )
            if not conversation:
                conversation = Conversation(
                    hotel_id=event.hotel_id,
                    guest_id=event.guest_id,
                    stay_id=event.stay_id,
                    channel="whatsapp",
                    status=ConversationStatus.OPEN,
                    current_handler="BOT",
                )
                db.add(conversation)
                db.commit()
                db.refresh(conversation)
            elif conversation.stay_id != event.stay_id:
                # Guest has a new stay - update conversation to point to new stay
                old_stay_id = conversation.stay_id
                conversation.stay_id = event.stay_id
                # Also update room_id from the new stay
                if stay and stay.room_id:
                    conversation.room_id = stay.room_id
                db.add(conversation)
                db.commit()
                logger.info(
                    f"Updated conversation {conversation.id} from stay {old_stay_id} to stay {event.stay_id}"
                )

            hotel = db.query(Hotel).filter(Hotel.id == event.hotel_id).first()
            language = event.guest.preferred_language or "en"

            # Get guest name and room number for PRO welcome
            guest_name = None
            room_number = ""
            if event.guest and event.guest.pii:
                guest_name = event.guest.pii.full_name
            if stay and stay.room:
                room_number = stay.room.room_number or ""

            # Build welcome message
            text = _get_template_text(event.journey.template_key, language)
            english_followup = None

            if hotel and event.journey and event.journey.template_key == "welcome_after_checkin":
                # Use personalized welcome message with guest name (PRO tier)
                text = _get_welcome_message(hotel, room_number, guest_name)

                # Check if bilingual welcome is enabled (send English follow-up for tourists)
                settings = hotel.settings or {}
                hotel_lang = hotel.staff_language or hotel.interface_language or "en"
                if settings.get("bilingual_welcome") and hotel_lang != "en":
                    english_followup = _get_english_followup(
                        hotel,
                        room_number,
                        guest_name,
                    )

            # 3. IDEMPOTENCY: Check if identical message was sent in last 5 minutes
            recent_cutoff = now - timedelta(minutes=5)
            existing_message = (
                db.query(Message)
                .filter(
                    Message.conversation_id == conversation.id,
                    Message.direction == MessageDirection.OUTGOING,
                    Message.text == text,
                    Message.created_at >= recent_cutoff,
                )
                .first()
            )
            if existing_message:
                # Message already sent recently, mark as SENT without resending
                event.status = JourneyEventStatus.SENT
                db.add(event)
                db.commit()
                logger.info(
                    f"Journey event {event.id} marked SENT (idempotency: message already exists)"
                )
                continue

            try:
                # Use provider factory for multi-provider support (Meta/Twilio)
                if hotel:
                    provider = get_message_provider(hotel)

                    # For WhatsApp welcome_after_checkin, use template messages
                    is_welcome = (
                        event.journey and event.journey.template_key == "welcome_after_checkin"
                    )
                    is_whatsapp = conversation.channel == "whatsapp"

                    # Determine message text for DB logging
                    if is_welcome and is_whatsapp:
                        # For templates, use hotel language (not phone prefix)
                        hotel_lang = hotel.staff_language or hotel.interface_language or "en"
                        lang_code = "ro" if hotel_lang == "ro" else "en_US"
                        tpl_name = "welcome_guest_" if hotel_lang == "ro" else "welcome_guest"
                        db_text = f"Welcome message sent ({hotel.name}, room {room_number})"
                    else:
                        db_text = text

                    # Save message to DB
                    bot_message = Message(
                        conversation_id=conversation.id,
                        sender_type=MessageSender.BOT,
                        direction=MessageDirection.OUTGOING,
                        text=db_text,
                    )
                    db.add(bot_message)
                    db.commit()

                    if is_welcome and is_whatsapp:
                        # PRO tier: Use WhatsApp Template Message (business-initiated)
                        # Templates are required when bot writes first (no 24h window)

                        # Use hotel language (already defined above)
                        # hotel_lang, lang_code already set in the DB logging block

                        # Template parameters: {{1}} = guest name, {{2}} = hotel name, {{3}} = room number
                        template_params = [
                            guest_name or "Guest",
                            hotel.name or "Hotel",
                            room_number or "",
                        ]

                        # Send template message (pre-approved in Meta Business Manager)
                        # Template name: "welcome_guest_" for Romanian, "welcome_guest" for others
                        template_name = "welcome_guest_" if hotel_lang == "ro" else "welcome_guest"
                        success = send_template_message(
                            wa_id=wa_id,
                            template_name=template_name,
                            language_code=lang_code,
                            parameters=template_params,
                            hotel=hotel,
                        )

                        # Bilingual welcome: if Romanian number AND checkbox is ON
                        # Send a second message in English
                        settings = hotel.settings or {}
                        bilingual_enabled = settings.get("bilingual_welcome", False)

                        if success and bilingual_enabled and lang_code == "ro":
                            import time

                            time.sleep(2)  # Delay between messages

                            # Send English version of the same template
                            followup_success = send_template_message(
                                wa_id=wa_id,
                                template_name="welcome_guest",
                                language_code="en_US",
                                parameters=template_params,
                                hotel=hotel,
                            )

                            if followup_success:
                                # Save English follow-up to DB for reference
                                followup_msg = Message(
                                    conversation_id=conversation.id,
                                    sender_type=MessageSender.BOT,
                                    direction=MessageDirection.OUTGOING,
                                    text="[Template: welcome_guest, lang: en]",
                                )
                                db.add(followup_msg)
                                db.commit()
                                logger.info(
                                    "Bilingual English template sent for event %s",
                                    event.id,
                                )
                    else:
                        # Other journey messages (non-welcome): use plain text
                        success = provider.send_text(phone_number=wa_id, message=text)

                    # 4. ATOMIC: Immediately commit SENT status after success
                    if success:
                        event.status = JourneyEventStatus.SENT
                        db.add(event)
                        db.commit()
                        logger.info(
                            "Journey message sent via %s for event %s to %s",
                            provider.provider_name,
                            event.id,
                            wa_id,
                        )
                    else:
                        # Mark as CANCELLED on failure to prevent infinite retries
                        event.status = JourneyEventStatus.CANCELLED
                        db.add(event)
                        db.commit()
                        logger.error(
                            "Failed to send journey message via %s for event %s, marked CANCELLED",
                            provider.provider_name,
                            event.id,
                        )
                else:
                    logger.error("Hotel not found for event %s", event.id)
            except Exception as exc:
                logger.exception("Failed to send journey message for event %s: %s", event.id, exc)
                # Mark as CANCELLED on exception to prevent infinite retries
                event.status = JourneyEventStatus.CANCELLED
                db.add(event)
                db.commit()

        # Job terminat - scheduler-ul extern îl va rula din nou
    finally:
        db.close()
