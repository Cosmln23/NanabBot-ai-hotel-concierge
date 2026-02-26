import hashlib
import logging
import re
from typing import Any, Dict, Optional

from fastapi import APIRouter, Depends, HTTPException, Request
from linebot import WebhookParser
from linebot.exceptions import InvalidSignatureError
from linebot.models import MessageEvent, TextMessage
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.core.config import get_settings
from app.core.db import get_db
from app.core.security import rate_limit
from app.models import (
    Conversation,
    ConversationStatus,
    Guest,
    GuestPII,
    Hotel,
    Message,
    MessageDirection,
    MessageSender,
)
from app.services.analytics import log_message_in
from app.services.identity_resolver import resolve_identity_by_line_user
from app.services.messaging.providers.line import LineProvider
from app.workers import jobs
from app.workers.queue import get_queue

router = APIRouter(tags=["webhook-line"])
logger = logging.getLogger("hotelbot.webhook.line")

PHONE_REGEX = re.compile(r"\+?\d[\d\s\-]{6,15}")


def _extract_phone_candidate(text: str) -> Optional[str]:
    """Extract a phone-like string to attempt matching guests."""
    if not text:
        return None
    match = PHONE_REGEX.search(text)
    if not match:
        return None
    candidate = match.group().strip()
    digits = re.sub(r"\D", "", candidate)
    if len(digits) < 8 or len(digits) > 15:
        return None
    # Preserve leading plus if present
    return candidate


def _get_line_provider(hotel: Hotel) -> LineProvider:
    """Instantiate LINE provider, raising if not configured."""
    return LineProvider(hotel)


def _get_or_create_conversation(
    db: Session, hotel_id: int, guest_id: int, stay_id: Optional[int] = None
) -> Conversation:
    convo = (
        db.query(Conversation)
        .filter(
            Conversation.hotel_id == hotel_id,
            Conversation.guest_id == guest_id,
            Conversation.channel == "line",
            Conversation.status == ConversationStatus.OPEN,
        )
        .order_by(Conversation.created_at.desc())
        .first()
    )
    if not convo:
        convo = Conversation(
            hotel_id=hotel_id,
            guest_id=guest_id,
            stay_id=stay_id,
            channel="line",
            status=ConversationStatus.OPEN,
            current_handler="BOT",
        )
        db.add(convo)
        db.commit()
        db.refresh(convo)
    elif stay_id and convo.stay_id != stay_id:
        # Guest has a new stay - update conversation to point to new stay
        from app.models import Stay

        convo.stay_id = stay_id
        # Also update room_id from the new stay
        new_stay = db.query(Stay).filter(Stay.id == stay_id).first()
        if new_stay and new_stay.room_id:
            convo.room_id = new_stay.room_id
        db.add(convo)
        db.commit()
        db.refresh(convo)
        logger.info(f"Updated LINE conversation {convo.id} to new stay {stay_id}")
    return convo


@router.post("/webhook/line/{hotel_id}")
async def receive_line_webhook(
    hotel_id: int,
    request: Request,
    db: Session = Depends(get_db),
):
    if request:
        rate_limit(f"webhook_line:{request.client.host}", limit=30, window_seconds=60)

    hotel: Optional[Hotel] = db.query(Hotel).filter(Hotel.id == hotel_id).first()
    if not hotel:
        raise HTTPException(status_code=404, detail="Hotel not found")

    hotel_settings: Dict[str, Any] = hotel.settings or {}
    channel_secret = hotel_settings.get("line_channel_secret")
    if not channel_secret:
        global_settings = get_settings()
        channel_secret = global_settings.line_channel_secret
    if not channel_secret:
        raise HTTPException(status_code=400, detail="LINE not configured for this hotel")

    signature = request.headers.get("X-Line-Signature")
    if not signature:
        raise HTTPException(status_code=400, detail="Missing LINE signature")

    body_bytes = await request.body()
    body_text = body_bytes.decode("utf-8")
    parser = WebhookParser(channel_secret)
    try:
        events = parser.parse(body_text, signature)
    except InvalidSignatureError:
        raise HTTPException(status_code=403, detail="Invalid signature")
    except Exception:
        raise HTTPException(status_code=400, detail="Invalid payload")

    provider: Optional[LineProvider] = None

    for event in events:
        if not isinstance(event, MessageEvent):
            continue
        if not isinstance(event.message, TextMessage):
            continue

        user_id = event.source.user_id if event.source else None
        if not user_id:
            continue

        text = event.message.text or ""
        raw_event = event.as_json_dict() if hasattr(event, "as_json_dict") else {}

        guest: Optional[Guest] = (
            db.query(Guest)
            .filter(Guest.hotel_id == hotel.id, Guest.line_user_id == user_id)
            .first()
        )

        # Unknown LINE user: create placeholder guest and enqueue for room-linking flow
        if not guest:
            # create placeholder guest tied to this hotel using hashed line user id
            line_hash = hashlib.sha256(f"line:{user_id}".encode()).hexdigest()
            guest = (
                db.query(Guest)
                .filter(Guest.hotel_id == hotel.id, Guest.phone_hash == line_hash)
                .first()
            )
            if not guest:
                guest = Guest(hotel_id=hotel.id, phone_hash=line_hash)
                db.add(guest)
                try:
                    db.commit()
                    db.refresh(guest)
                except IntegrityError:
                    db.rollback()
                    guest = (
                        db.query(Guest)
                        .filter(Guest.hotel_id == hotel.id, Guest.phone_hash == line_hash)
                        .first()
                    )
                    if not guest:
                        raise

        # Known LINE user: route to brain for processing
        if guest.line_user_id:
            try:
                context = resolve_identity_by_line_user(db, user_id, hotel_id=hotel.id)
            except Exception:
                continue
            conversation = _get_or_create_conversation(
                db,
                hotel_id=hotel.id,
                guest_id=context.guest.id,
                stay_id=context.stay.id if context.stay else None,
            )
        else:
            # Placeholder guest (not yet linked); create a conversation to allow worker linking flow
            conversation = _get_or_create_conversation(
                db,
                hotel_id=hotel.id,
                guest_id=guest.id,
                stay_id=None,
            )

        # Fetch LINE display name if not already stored (defensive - silent fail)
        try:
            if not (guest.pii and guest.pii.full_name):
                if not provider:
                    provider = _get_line_provider(hotel)
                profile = provider.get_user_profile(user_id)
                display_name = profile.get("display_name")
                if display_name:
                    if not guest.pii:
                        guest.pii = GuestPII(guest_id=guest.id, full_name=display_name)
                        db.add(guest.pii)
                    else:
                        guest.pii.full_name = display_name
                        db.add(guest.pii)
                    db.commit()
                    logger.debug(
                        "LINE: Stored display name '%s' for guest %s",
                        display_name,
                        guest.id,
                    )
        except Exception as e:
            logger.debug("LINE: Could not store display name for guest %s: %s", guest.id, e)
            # Silent fail - not critical, continue processing

        msg = Message(
            conversation_id=conversation.id,
            sender_type=MessageSender.GUEST,
            direction=MessageDirection.INCOMING,
            text=text,
            raw_payload_json={
                "line_user_id": user_id,
                "source": raw_event.get("source"),
                "event": raw_event,
            },
        )
        db.add(msg)
        db.commit()

        try:
            log_message_in(db, hotel_id=hotel.id, metadata={"conversation_id": conversation.id})
        except Exception as exc:
            logger.warning(
                "Failed to log incoming LINE message for conversation %s: %s",
                conversation.id,
                exc,
            )

        try:
            queue = get_queue()
            queue.enqueue(jobs.process_incoming_message, msg.id)
        except Exception as exc:
            logger.warning("Failed to enqueue LINE message job: %s", exc)

    return {"status": "received"}
