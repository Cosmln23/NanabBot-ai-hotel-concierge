"""
WhatsApp Webhook - Receives messages and queues for processing.
"""

import logging
import re
from typing import Any, Dict, Optional

from fastapi import APIRouter, Depends, HTTPException, Request
from fastapi.responses import PlainTextResponse
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.core.config import get_settings
from app.core.db import get_db
from app.core.security import rate_limit
from app.models import (
    Conversation,
    ConversationStatus,
    Hotel,
    Message,
    MessageDirection,
    MessageSender,
)
from app.services.analytics import log_message_in
from app.services.identity_resolver import resolve_identity
from app.services.whatsapp_client import send_text_message
from app.services.whatsapp_gateway import parse_payload
from app.workers import jobs
from app.workers.queue import get_queue

router = APIRouter(tags=["webhook"])
logger = logging.getLogger("hotelbot.webhook.wa")

settings = get_settings()


def get_or_create_conversation(
    db: Session, hotel_id: int, guest_id: int, stay_id: Optional[int] = None
) -> Conversation:
    """Get existing open conversation or create a new one."""
    convo = (
        db.query(Conversation)
        .filter(
            Conversation.hotel_id == hotel_id,
            Conversation.guest_id == guest_id,
            Conversation.channel == "whatsapp",
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
            channel="whatsapp",
            status=ConversationStatus.OPEN,
            current_handler="BOT",
        )
        db.add(convo)
        try:
            db.commit()
            db.refresh(convo)
        except IntegrityError:
            db.rollback()
            convo = (
                db.query(Conversation)
                .filter(
                    Conversation.hotel_id == hotel_id,
                    Conversation.guest_id == guest_id,
                    Conversation.channel == "whatsapp",
                    Conversation.status == ConversationStatus.OPEN,
                )
                .order_by(Conversation.created_at.desc())
                .first()
            )
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
        logger.info(f"Updated conversation {convo.id} to new stay {stay_id}")
    return convo


@router.get("/webhook/whatsapp/{hotel_id}")
def verify_whatsapp_webhook(
    hotel_id: int,
    request: Request,
    db: Session = Depends(get_db),
):
    """Webhook verification with per-hotel verify token support (BYON)."""
    mode = request.query_params.get("hub.mode")
    token = request.query_params.get("hub.verify_token")
    challenge = request.query_params.get("hub.challenge")

    hotel = db.query(Hotel).filter(Hotel.id == hotel_id).first()
    verify_token = settings.whatsapp_verify_token

    if hotel:
        hotel_settings = hotel.settings or {}
        hotel_verify_token = hotel_settings.get("whatsapp_verify_token")
        has_byon = bool(hotel_settings.get("whatsapp_access_token"))
        if has_byon and hotel_verify_token:
            verify_token = hotel_verify_token

    if mode == "subscribe" and token and verify_token and token == verify_token:
        logger.info("WhatsApp webhook verified for hotel_id=%s", hotel_id)
        return PlainTextResponse(challenge or "")

    logger.warning("WhatsApp webhook verification failed for hotel_id=%s", hotel_id)
    raise HTTPException(status_code=403, detail="Verification failed")


@router.get("/webhook/whatsapp")
def verify_whatsapp_webhook_default(request: Request, db: Session = Depends(get_db)):
    """Webhook verification without hotel_id - uses DEFAULT_HOTEL_ID"""
    return verify_whatsapp_webhook(settings.default_hotel_id, request, db)


@router.post("/webhook/whatsapp/{hotel_id}")
def receive_whatsapp_webhook(
    hotel_id: int,
    payload: Dict[str, Any],
    db: Session = Depends(get_db),
    request: Request = None,
):
    """Receive WhatsApp message and queue for processing."""
    if request:
        rate_limit(f"webhook:{request.client.host}", limit=30, window_seconds=60)

    incoming = parse_payload(payload)
    if not incoming or not incoming.wa_id:
        raise HTTPException(status_code=400, detail="Invalid payload")

    # DEDUPLICATION: Check if this WhatsApp message_id was already processed
    if incoming.message_id:
        existing_msg = (
            db.query(Message)
            .filter(
                Message.direction == MessageDirection.INCOMING,
                Message.raw_payload_json["id"].astext == incoming.message_id,
            )
            .first()
        )
        if existing_msg:
            logger.info(f"Duplicate WhatsApp message ignored: message_id={incoming.message_id}")
            return {"status": "received"}

    context = resolve_identity(db, wa_id=incoming.wa_id, hotel_id=hotel_id)
    if not context:
        # Hotel does not exist (deleted or invalid QR code)
        try:
            send_text_message(
                incoming.wa_id,
                "This QR code is no longer valid. Please contact the hotel reception.",
            )
        except Exception as e:
            logger.error(f"Failed to send invalid QR message: {e}")
        return {"status": "invalid_hotel"}

    conversation = get_or_create_conversation(
        db,
        context.hotel.id,
        context.guest.id,
        stay_id=context.stay.id if context.stay else None,
    )

    # SPAM PROTECTION: Ignore identical text sent within 30 seconds
    if incoming.text:
        from datetime import datetime, timedelta, timezone

        recent_cutoff = datetime.now(timezone.utc) - timedelta(seconds=30)
        recent_same_text = (
            db.query(Message)
            .filter(
                Message.conversation_id == conversation.id,
                Message.direction == MessageDirection.INCOMING,
                Message.text == incoming.text,
                Message.created_at >= recent_cutoff,
            )
            .first()
        )
        if recent_same_text:
            logger.info(f"Spam detected: same text within 30s, conversation_id={conversation.id}")
            return {"status": "received"}

    msg = Message(
        conversation_id=conversation.id,
        sender_type=MessageSender.GUEST,
        direction=MessageDirection.INCOMING,
        text=incoming.text or "",
        raw_payload_json=incoming.raw_value,
    )
    db.add(msg)
    db.commit()

    try:
        log_message_in(db, hotel_id=context.hotel.id, metadata={"conversation_id": conversation.id})
    except Exception as exc:
        logger.warning("Failed to log message: %s", exc)

    try:
        queue = get_queue()
        queue.enqueue(jobs.process_incoming_message, msg.id)
    except Exception as exc:
        logger.error("Failed to enqueue message job: %s", exc)

    return {"status": "received"}


@router.post("/webhook/whatsapp")
def receive_whatsapp_webhook_default(
    payload: Dict[str, Any],
    db: Session = Depends(get_db),
    request: Request = None,
):
    """
    Webhook POST without hotel_id in URL.

    Multi-tenant routing for WhatsApp BASIC tier:
    1. Extract #hotel_id from QR code message (e.g., "Conectează Camera 1 #13")
    2. If found, route to that hotel
    3. If not found, search for existing conversation by wa_id
    4. If no existing conversation and no #hotel_id, ignore (user must scan QR)
    """
    incoming = parse_payload(payload)
    if not incoming or not incoming.wa_id:
        # Invalid payload or status update - ignore silently
        return {"status": "ignored"}

    # 1. Try to extract #hotel_id and !token from message text (QR code scan)
    hotel_id = None
    qr_token = None
    if incoming.text:
        # Try format with token first: "Connect Room 101 #4 !a7b3c"
        match_with_token = re.search(r"#(\d+)\s+!([a-f0-9]+)\s*$", incoming.text.strip())
        if match_with_token:
            hotel_id = int(match_with_token.group(1))
            qr_token = match_with_token.group(2)
            logger.info(
                f"WhatsApp multi-tenant: extracted hotel_id={hotel_id} with token from QR message"
            )
        else:
            # Legacy format without token: "Connect Room 101 #4"
            match = re.search(r"#(\d+)\s*$", incoming.text.strip())
            if match:
                hotel_id = int(match.group(1))
                logger.info(
                    f"WhatsApp multi-tenant: extracted hotel_id={hotel_id} from QR message (no token)"
                )

    # 1b. Validate QR token if hotel_id was extracted from message
    if hotel_id and qr_token is not None:
        hotel = db.query(Hotel).filter(Hotel.id == hotel_id).first()
        if hotel:
            hotel_settings = hotel.settings or {}
            qr_tokens = hotel_settings.get("qr_tokens", {})
            if qr_token not in qr_tokens:
                logger.warning(f"WhatsApp: invalid QR token '{qr_token}' for hotel_id={hotel_id}")
                try:
                    send_text_message(
                        incoming.wa_id,
                        "This QR code is not valid. Please scan the QR code in your room.",
                    )
                except Exception as e:
                    logger.error(f"Failed to send invalid token message: {e}")
                return {"status": "invalid_token"}
    elif hotel_id and qr_token is None:
        # Message has #hotel_id but no !token — could be spoofed manually
        hotel = db.query(Hotel).filter(Hotel.id == hotel_id).first()
        if hotel:
            hotel_settings = hotel.settings or {}
            qr_tokens = hotel_settings.get("qr_tokens", {})
            # If hotel has QR tokens configured, require token (reject manual spoofing)
            if qr_tokens:
                logger.warning(
                    f"WhatsApp: missing QR token for hotel_id={hotel_id} (spoofing attempt?)"
                )
                try:
                    send_text_message(
                        incoming.wa_id, "Please scan the QR code in your room to connect."
                    )
                except Exception as e:
                    logger.error(f"Failed to send missing token message: {e}")
                return {"status": "missing_token"}

    # 2. If no #hotel_id, try to find existing conversation by wa_id
    if not hotel_id:
        import hashlib

        from app.services.identity_resolver import phone_variants

        variants = phone_variants(incoming.wa_id)
        variant_hashes = [hashlib.sha256(v.encode()).hexdigest() for v in variants]

        from app.models import Guest

        existing_conv = (
            db.query(Conversation)
            .join(Guest, Conversation.guest_id == Guest.id)
            .filter(
                Conversation.channel == "whatsapp",
                Conversation.status == ConversationStatus.OPEN,
                Guest.phone_hash.in_(variant_hashes),
            )
            .order_by(Conversation.updated_at.desc())
            .first()
        )

        if existing_conv:
            hotel_id = existing_conv.hotel_id
            logger.info(
                f"WhatsApp multi-tenant: found existing conversation for hotel_id={hotel_id}"
            )

    # 3. If still no hotel_id, send "scan QR" message and ignore
    if not hotel_id:
        logger.info(
            f"WhatsApp: no hotel_id and no existing conversation for wa_id={incoming.wa_id[:6]}... - sending scan QR message"
        )
        try:
            # Send bilingual "scan QR" message (EN + RO for shared number)
            scan_msg = "Please scan the QR code in your room to connect with the hotel."
            send_text_message(incoming.wa_id, scan_msg)
        except Exception as e:
            logger.error(f"Failed to send scan QR message: {e}")
        return {"status": "sent_scan_qr"}

    return receive_whatsapp_webhook(hotel_id, payload, db, request)
