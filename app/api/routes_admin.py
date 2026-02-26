import html
from datetime import datetime, timezone
from typing import Optional

from fastapi import APIRouter, Body, Depends, HTTPException, Request
from fastapi.responses import HTMLResponse
from sqlalchemy import func
from sqlalchemy.orm import Session, joinedload

from app.core.config import get_settings
from app.core.db import get_db
from app.core.logging import logger
from app.core.security import decode_access_token, get_bearer_token
from app.models import GuestPII  # noqa: F401
from app.models import (
    Conversation,
    ConversationStatus,
    Guest,
    Hotel,
    Message,
    MessageDirection,
    MessageSender,
    StaffUser,
    Stay,
    Task,
    TaskStatus,
)
from app.services.analytics import log_task_done
from app.services.identity_resolver import determine_state
from app.services.messaging.factory import get_message_provider

settings = get_settings()
router = APIRouter(prefix="/admin", tags=["admin"])


def require_staff(request: Request, db: Session = Depends(get_db)) -> StaffUser:
    token = get_bearer_token(request)
    if not token:
        # fallback to legacy admin token only in development
        legacy = request.headers.get("Authorization", "")
        if (
            settings.environment == "development"
            and legacy.replace("Bearer", "").strip() == settings.admin_token
        ):
            logger.info(
                "Admin legacy token access to %s from %s",
                request.url.path,
                request.client.host,
            )
            request.state.user = None
            return None  # type: ignore[return-value]
        raise HTTPException(status_code=401, detail="Unauthorized")
    payload = decode_access_token(token)
    user = (
        db.query(StaffUser)
        .filter(StaffUser.id == int(payload.get("sub")), StaffUser.is_active == True)  # noqa: E712
        .first()
    )
    if not user:
        raise HTTPException(status_code=401, detail="Unauthorized")
    request.state.user = user
    logger.info(
        "Admin access to %s by user %s from %s",
        request.url.path,
        user.email,
        request.client.host,
    )
    return user


@router.get("/ui-config")
def admin_ui_config(db: Session = Depends(get_db), _user=Depends(require_staff)):
    """Expose UI configuration (language + lock) for the current staff's hotel."""
    hotel = db.query(Hotel).filter(Hotel.id == _user.hotel_id).first() if _user else None
    return {
        "interface_language": hotel.interface_language if hotel else "en",
        "language_locked": hotel.language_locked if hotel else False,
    }


@router.get("/subscription-status")
def get_subscription_status(db: Session = Depends(get_db), _user=Depends(require_staff)):
    """Get subscription status for trial banner display."""
    if not _user:
        raise HTTPException(status_code=401, detail="Unauthorized")

    hotel = db.query(Hotel).filter(Hotel.id == _user.hotel_id).first()
    if not hotel:
        raise HTTPException(status_code=404, detail="Hotel not found")

    tier = hotel.subscription_tier or "free"
    trial_ends_at = hotel.trial_ends_at
    days_remaining = None
    is_expired = False

    if tier == "free" and trial_ends_at:
        now = datetime.now(timezone.utc)
        if trial_ends_at.tzinfo is None:
            from datetime import timezone as tz

            trial_ends_at = trial_ends_at.replace(tzinfo=tz.utc)
        delta = trial_ends_at - now
        days_remaining = max(0, delta.days)
        is_expired = delta.total_seconds() < 0

    return {
        "tier": tier,
        "trial_ends_at": trial_ends_at.isoformat() if trial_ends_at else None,
        "days_remaining": days_remaining,
        "is_expired": is_expired,
    }


@router.get("/conversations")
def list_conversations(
    page: int = 1,
    limit: int = 25,
    db: Session = Depends(get_db),
    _user=Depends(require_staff),
):
    # SECURITY FIX: Filter by hotel_id to prevent multi-tenancy data leak
    if not _user:
        raise HTTPException(status_code=401, detail="Unauthorized")

    # Calculate offset for pagination
    offset = (page - 1) * limit

    # Get total count for pagination (exclude GDPR-deleted guests)
    total_count = (
        db.query(Conversation)
        .join(Guest)
        .filter(
            Conversation.hotel_id == _user.hotel_id,
            ~Guest.phone_hash.like("GDPR_DELETED_%"),
        )
        .count()
    )
    total_pages = (total_count + limit - 1) // limit  # Ceiling division

    # Optimized query with eager loading to avoid N+1 queries
    # Exclude conversations for GDPR-deleted guests
    conversations = (
        db.query(Conversation)
        .join(Guest)
        .filter(
            Conversation.hotel_id == _user.hotel_id,
            ~Guest.phone_hash.like("GDPR_DELETED_%"),
        )
        .options(
            joinedload(Conversation.guest).joinedload(Guest.pii),
            joinedload(Conversation.stay).joinedload(Stay.room),
            joinedload(Conversation.room),
        )
        .order_by(Conversation.updated_at.desc())
        .offset(offset)
        .limit(limit)
        .all()
    )

    # Get conversation IDs for batch queries
    conv_ids = [c.id for c in conversations]
    stay_ids = [c.stay_id for c in conversations if c.stay_id]

    # Batch query: last message per conversation (subquery)
    last_messages = {}
    if conv_ids:
        # Subquery to get max created_at per conversation
        subq = (
            db.query(
                Message.conversation_id,
                func.max(Message.created_at).label("max_created"),
            )
            .filter(Message.conversation_id.in_(conv_ids))
            .group_by(Message.conversation_id)
            .subquery()
        )
        # Join to get actual message text
        msgs = (
            db.query(Message.conversation_id, Message.text)
            .join(
                subq,
                (Message.conversation_id == subq.c.conversation_id)
                & (Message.created_at == subq.c.max_created),
            )
            .all()
        )
        last_messages = {m.conversation_id: m.text for m in msgs}

    # Batch query: open tasks count per stay
    open_tasks = {}
    if stay_ids:
        tasks_count = (
            db.query(Task.stay_id, func.count(Task.id).label("cnt"))
            .filter(Task.stay_id.in_(stay_ids), Task.status == TaskStatus.OPEN)
            .group_by(Task.stay_id)
            .all()
        )
        open_tasks = {t.stay_id: t.cnt for t in tasks_count}

    results = []
    for c in conversations:
        state = determine_state(c.stay)
        results.append(
            {
                "id": c.id,
                "hotel_id": c.hotel_id,
                "guest_id": c.guest_id,
                "stay_id": c.stay_id,
                "channel": c.channel,
                "status": (
                    c.status.value if isinstance(c.status, ConversationStatus) else c.status
                ),
                "current_handler": c.current_handler,
                "created_at": c.created_at,
                "updated_at": c.updated_at,
                "last_message_text": last_messages.get(c.id),
                "guest_state": state.value if hasattr(state, "value") else state,
                "open_tasks_count": open_tasks.get(c.stay_id, 0) if c.stay_id else 0,
                "guest_name": (c.guest.pii.full_name if c.guest and c.guest.pii else None),
                "guest_phone": (c.guest.pii.phone_plain if c.guest and c.guest.pii else None),
                "line_user_id": c.guest.line_user_id if c.guest else None,
                "room_number": (c.stay.room.room_number if c.stay and c.stay.room else None)
                or (c.room.room_number if c.room else None),
                "is_bot_paused": getattr(c, "is_bot_paused", False),
            }
        )
    return {
        "conversations": results,
        "pagination": {
            "page": page,
            "limit": limit,
            "total_count": total_count,
            "total_pages": total_pages,
        },
    }


@router.get("/conversations/{conversation_id}")
def get_conversation(
    conversation_id: int,
    db: Session = Depends(get_db),
    _user=Depends(require_staff),
):
    # SECURITY FIX: Verify conversation belongs to user's hotel
    if not _user:
        raise HTTPException(status_code=401, detail="Unauthorized")

    conversation = (
        db.query(Conversation)
        .filter(Conversation.id == conversation_id, Conversation.hotel_id == _user.hotel_id)
        .first()
    )
    if not conversation:
        raise HTTPException(status_code=404, detail="Conversation not found")
    messages = (
        db.query(Message)
        .filter(Message.conversation_id == conversation.id)
        .order_by(Message.created_at.asc())
        .all()
    )
    state = determine_state(conversation.stay)

    tasks = []
    if conversation.stay_id:
        tasks = (
            db.query(Task)
            .filter(Task.stay_id == conversation.stay_id)
            .order_by(Task.created_at.desc())
            .all()
        )

    return {
        "conversation": {
            "id": conversation.id,
            "hotel_id": conversation.hotel_id,
            "guest_id": conversation.guest_id,
            "stay_id": conversation.stay_id,
            "channel": conversation.channel,
            "status": (
                conversation.status.value
                if isinstance(conversation.status, ConversationStatus)
                else conversation.status
            ),
            "current_handler": conversation.current_handler,
            "is_bot_paused": getattr(conversation, "is_bot_paused", False),
            "created_at": conversation.created_at,
            "updated_at": conversation.updated_at,
            "guest_state": state.value if hasattr(state, "value") else state,
            "guest_name": (
                conversation.guest.pii.full_name
                if conversation.guest and conversation.guest.pii
                else None
            ),
            "room_number": (
                conversation.stay.room.room_number
                if conversation.stay and conversation.stay.room
                else None
            ),
        },
        "messages": [
            {
                "id": m.id,
                "sender_type": (
                    m.sender_type.value if hasattr(m.sender_type, "value") else m.sender_type
                ),
                "direction": (m.direction.value if hasattr(m.direction, "value") else m.direction),
                "text": m.text,
                "created_at": m.created_at,
            }
            for m in messages
        ],
        "tasks": [
            {
                "id": t.id,
                "type": t.type.value if hasattr(t.type, "value") else t.type,
                "status": t.status.value if hasattr(t.status, "value") else t.status,
                "payload_json": t.payload_json,
                "created_at": t.created_at,
                "completed_at": t.completed_at,
            }
            for t in tasks
        ],
    }


@router.get("/tasks")
def list_tasks(
    status: Optional[str] = None,
    db: Session = Depends(get_db),
    _user=Depends(require_staff),
):
    # SECURITY FIX: Filter by hotel_id to prevent multi-tenancy data leak
    if not _user:
        raise HTTPException(status_code=401, detail="Unauthorized")

    query = db.query(Task).filter(Task.hotel_id == _user.hotel_id)
    if status:
        try:
            status_enum = TaskStatus(status.upper())
        except ValueError:
            raise HTTPException(status_code=400, detail="Invalid status filter")
        query = query.filter(Task.status == status_enum)
    tasks = query.order_by(Task.created_at.desc()).all()
    return [
        {
            "id": t.id,
            "hotel_id": t.hotel_id,
            "stay_id": t.stay_id,
            "type": t.type.value if hasattr(t.type, "value") else t.type,
            "status": t.status.value if hasattr(t.status, "value") else t.status,
            "payload_json": t.payload_json,
            "staff_summary": getattr(t, "staff_summary", None),
            "priority": getattr(t, "priority", None),
            "created_at": t.created_at,
            "completed_at": t.completed_at,
        }
        for t in tasks
    ]


@router.post("/conversations/{conversation_id}/toggle-pause")
def toggle_pause(
    conversation_id: int,
    payload: dict = Body(...),
    db: Session = Depends(get_db),
    _user=Depends(require_staff),
):
    if not _user:
        raise HTTPException(status_code=401, detail="Unauthorized")
    paused = bool(payload.get("paused"))
    conversation = (
        db.query(Conversation)
        .filter(Conversation.id == conversation_id, Conversation.hotel_id == _user.hotel_id)
        .first()
    )
    if not conversation:
        raise HTTPException(status_code=404, detail="Conversation not found")

    conversation.is_bot_paused = paused
    conversation.current_handler = "STAFF" if paused else "BOT"
    db.add(conversation)
    db.commit()
    db.refresh(conversation)

    # Send system message to guest
    try:
        provider = get_message_provider(conversation.hotel)
        wa_id = None
        # extract wa_id or line_user_id from last incoming
        last_incoming = (
            db.query(Message)
            .filter(
                Message.conversation_id == conversation.id,
                Message.direction == MessageDirection.INCOMING,
            )
            .order_by(Message.created_at.desc())
            .first()
        )
        if last_incoming and last_incoming.raw_payload_json:
            payload_json = last_incoming.raw_payload_json
            if isinstance(payload_json, dict):
                wa_id = (
                    payload_json.get("from")
                    or payload_json.get("wa_id")
                    or payload_json.get("line_user_id")
                )
                contacts = payload_json.get("contacts", [])
                if not wa_id and contacts:
                    wa_id = contacts[0].get("wa_id")
                source = payload_json.get("source") or {}
                if not wa_id and source.get("userId"):
                    wa_id = source.get("userId")
        if not wa_id and conversation.guest and conversation.guest.pii:
            wa_id = conversation.guest.pii.phone_plain

        # Thai hotels (LINE) - ALWAYS bilingual TH/EN for all guests (staff needs to read too)
        hotel = conversation.hotel
        if hotel and hotel.staff_language == "th":
            takeover_msg = (
                "พนักงานได้เข้าร่วมการสนทนาแล้ว / A staff member has joined the conversation."
            )
            resume_msg = "การสนทนาได้กลับไปยังผู้ช่วยเสมือนแล้ว / The conversation has returned to the virtual assistant."
            system_msg = takeover_msg if paused else resume_msg
        else:
            # Other hotels - use guest language
            guest_lang = (
                (conversation.guest.preferred_language if conversation.guest else None)
                or (hotel.staff_language if hotel else None)
                or "en"
            )
            takeover_msgs = {
                "en": "A staff member has joined the conversation. You're now chatting directly with the hotel.",
                "ro": "Un membru al echipei a intrat în conversație. Comunici direct cu hotelul acum.",
            }
            resume_msgs = {
                "en": "The conversation has returned to the virtual assistant.",
                "ro": "Conversația a revenit la asistentul virtual.",
            }
            system_msg = (
                takeover_msgs.get(guest_lang, takeover_msgs["en"])
                if paused
                else resume_msgs.get(guest_lang, resume_msgs["en"])
            )
        if wa_id:
            provider.send_text(phone_number=wa_id, message=system_msg)
        # log in DB as STAFF outgoing
        msg = Message(
            conversation_id=conversation.id,
            sender_type=MessageSender.STAFF,
            direction=MessageDirection.OUTGOING,
            text=system_msg,
        )
        db.add(msg)
        db.commit()
    except Exception as e:
        logger.error("Failed to send system message on pause toggle: %s", e)

    return {"paused": conversation.is_bot_paused}


@router.post("/conversations/{conversation_id}/send-message")
def send_manual_message(
    conversation_id: int,
    payload: dict = Body(...),
    db: Session = Depends(get_db),
    _user=Depends(require_staff),
):
    if not _user:
        raise HTTPException(status_code=401, detail="Unauthorized")

    text = payload.get("message")
    if not text:
        raise HTTPException(status_code=400, detail="Message is required")

    conversation = (
        db.query(Conversation)
        .filter(Conversation.id == conversation_id, Conversation.hotel_id == _user.hotel_id)
        .first()
    )
    if not conversation:
        raise HTTPException(status_code=404, detail="Conversation not found")

    wa_id = None
    last_incoming = (
        db.query(Message)
        .filter(
            Message.conversation_id == conversation.id,
            Message.direction == MessageDirection.INCOMING,
        )
        .order_by(Message.created_at.desc())
        .first()
    )
    if last_incoming and last_incoming.raw_payload_json:
        payload_json = last_incoming.raw_payload_json
        if isinstance(payload_json, dict):
            wa_id = (
                payload_json.get("from")
                or payload_json.get("wa_id")
                or payload_json.get("line_user_id")
            )
            contacts = payload_json.get("contacts", [])
            if not wa_id and contacts:
                wa_id = contacts[0].get("wa_id")
            source = payload_json.get("source") or {}
            if not wa_id and source.get("userId"):
                wa_id = source.get("userId")
    if not wa_id and conversation.guest and conversation.guest.pii:
        wa_id = conversation.guest.pii.phone_plain

    try:
        provider = get_message_provider(conversation.hotel)
        if wa_id:
            provider.send_text(phone_number=wa_id, message=text)
        else:
            logger.warning(
                "No destination phone/user id found for conversation %s",
                conversation.id,
            )
        msg = Message(
            conversation_id=conversation.id,
            sender_type=MessageSender.STAFF,
            direction=MessageDirection.OUTGOING,
            text=text,
        )
        db.add(msg)
        db.commit()
    except Exception as e:
        logger.error("Manual send failed for conversation %s: %s", conversation.id, e)
        raise HTTPException(status_code=500, detail="Failed to send message")

    return {"sent": True}


@router.patch("/tasks/{task_id}")
def mark_task_done(
    task_id: int,
    status: str = Body("DONE"),
    db: Session = Depends(get_db),
    _user=Depends(require_staff),
):
    # SECURITY FIX: Verify task belongs to user's hotel
    if not _user:
        raise HTTPException(status_code=401, detail="Unauthorized")

    task = db.query(Task).filter(Task.id == task_id, Task.hotel_id == _user.hotel_id).first()
    if not task:
        raise HTTPException(status_code=404, detail="Task not found")

    status_value = (status or "DONE").upper()
    try:
        new_status = TaskStatus(status_value)
    except ValueError:
        raise HTTPException(status_code=400, detail="Invalid status")

    task.status = new_status
    if new_status == TaskStatus.DONE:
        task.completed_at = datetime.now(timezone.utc)
    db.add(task)
    db.commit()
    try:
        log_task_done(db, hotel_id=task.hotel_id, metadata={"task_id": task.id})
    except Exception as exc:
        logger.warning("Failed to log task done for task %s: %s", task.id, exc)
    db.refresh(task)
    return {
        "id": task.id,
        "status": task.status.value if hasattr(task.status, "value") else task.status,
        "completed_at": task.completed_at,
    }


# ---------------------------------------------------------------------------
# GDPR Data Subject Rights
# ---------------------------------------------------------------------------


@router.get("/guests/{guest_id}/export")
def gdpr_export_guest(
    guest_id: int,
    db: Session = Depends(get_db),
    _user=Depends(require_staff),
):
    """
    GDPR Data Export — returns all data for a guest (PII decrypted).
    Only accessible by authenticated staff for their own hotel.
    """
    if not _user:
        raise HTTPException(status_code=401, detail="Unauthorized")

    guest = (
        db.query(Guest)
        .filter(Guest.id == guest_id, Guest.hotel_id == _user.hotel_id)
        .options(joinedload(Guest.pii))
        .first()
    )
    if not guest:
        raise HTTPException(status_code=404, detail="Guest not found")

    # Guest PII (decrypted by ORM)
    pii_data = None
    if guest.pii:
        pii_data = {
            "full_name": guest.pii.full_name,
            "phone_plain": guest.pii.phone_plain,
            "email_plain": guest.pii.email_plain,
            "other_pii_json": guest.pii.other_pii_json,
        }

    # Stays
    stays = db.query(Stay).filter(Stay.guest_id == guest_id, Stay.hotel_id == _user.hotel_id).all()
    stays_data = [
        {
            "id": s.id,
            "room_id": s.room_id,
            "checkin_date": s.checkin_date.isoformat() if s.checkin_date else None,
            "checkout_date": s.checkout_date.isoformat() if s.checkout_date else None,
            "status": s.status.value if hasattr(s.status, "value") else s.status,
            "channel": s.channel,
        }
        for s in stays
    ]

    # Conversations + Messages (eager-loaded to avoid N+1 queries)
    conversations = (
        db.query(Conversation)
        .filter(Conversation.guest_id == guest_id, Conversation.hotel_id == _user.hotel_id)
        .options(joinedload(Conversation.messages))
        .all()
    )
    conversations_data = []
    for c in conversations:
        sorted_messages = sorted(c.messages, key=lambda m: m.created_at or datetime.min)
        conversations_data.append(
            {
                "id": c.id,
                "channel": c.channel,
                "status": c.status.value if hasattr(c.status, "value") else c.status,
                "created_at": c.created_at.isoformat() if c.created_at else None,
                "messages": [
                    {
                        "id": m.id,
                        "sender_type": (
                            m.sender_type.value
                            if hasattr(m.sender_type, "value")
                            else m.sender_type
                        ),
                        "direction": (
                            m.direction.value if hasattr(m.direction, "value") else m.direction
                        ),
                        "text": m.text,
                        "created_at": (m.created_at.isoformat() if m.created_at else None),
                    }
                    for m in sorted_messages
                ],
            }
        )

    # Hotel name for the export header
    hotel = db.query(Hotel).filter(Hotel.id == _user.hotel_id).first()
    hotel_name = html.escape(hotel.name) if hotel and hotel.name else "Hotel"
    export_date = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M UTC")

    # --- Escape all user-generated data ---
    def esc(val: object) -> str:
        return html.escape(str(val)) if val is not None else "—"

    # PII section
    pii_html = ""
    if pii_data:
        pii_html = f"""
        <div class="section">
          <h2>Personal Data</h2>
          <table><tbody>
            <tr><td class="label">Full Name</td><td>{esc(pii_data.get("full_name"))}</td></tr>
            <tr><td class="label">Phone</td><td>{esc(pii_data.get("phone_plain"))}</td></tr>
            <tr><td class="label">Email</td><td>{esc(pii_data.get("email_plain"))}</td></tr>
          </tbody></table>
        </div>"""
    else:
        pii_html = '<div class="section"><h2>Personal Data</h2><p>No PII on record.</p></div>'

    # Stays section
    stays_rows = ""
    for s in stays_data:
        stays_rows += (
            f"<tr>"
            f"<td>{esc(s.get('room_id'))}</td>"
            f"<td>{esc(s.get('checkin_date'))}</td>"
            f"<td>{esc(s.get('checkout_date'))}</td>"
            f"<td>{esc(s.get('status'))}</td>"
            f"<td>{esc(s.get('channel'))}</td>"
            f"</tr>"
        )
    stays_html = f"""
    <div class="section">
      <h2>Stays</h2>
      {"<p>No stays on record.</p>" if not stays_data else
       '<table><thead><tr><th>Room</th><th>Check-in</th><th>Check-out</th><th>Status</th><th>Channel</th></tr></thead><tbody>'
       + stays_rows + '</tbody></table>'}
    </div>"""

    # Conversations section
    convos_html = ""
    if not conversations_data:
        convos_html = (
            '<div class="section"><h2>Conversations</h2><p>No conversations on record.</p></div>'
        )
    else:
        for c in conversations_data:
            msgs_html = ""
            for m in c.get("messages", []):
                sender = esc(m.get("sender_type"))
                text = esc(m.get("text"))
                ts = esc(m.get("created_at"))
                msgs_html += f'<div class="msg"><span class="sender">{sender}</span> <span class="ts">{ts}</span><p>{text}</p></div>'
            convos_html += (
                f'<div class="section">'
                f'<h2>Conversation #{esc(c.get("id"))} — {esc(c.get("channel"))} ({esc(c.get("status"))})</h2>'
                f'<p class="ts">Started: {esc(c.get("created_at"))}</p>'
                f"{msgs_html}</div>"
            )

    html_content = f"""<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>GDPR Export — Guest {guest_id}</title>
<style>
  @import url('https://fonts.googleapis.com/css2?family=Inter:wght@400;600;700&display=swap');
  *{{margin:0;padding:0;box-sizing:border-box}}
  body{{font-family:'Inter',sans-serif;color:#44403c;background:#fafaf9;padding:2rem;line-height:1.6}}
  .header{{display:flex;justify-content:space-between;align-items:center;border-bottom:2px solid #d6d3d1;padding-bottom:1rem;margin-bottom:2rem}}
  .header h1{{font-size:1.5rem;color:#292524}}
  .header .meta{{text-align:right;font-size:.85rem;color:#78716c}}
  .section{{background:#fff;border:1px solid #e7e5e4;border-radius:8px;padding:1.25rem;margin-bottom:1.5rem}}
  .section h2{{font-size:1.1rem;color:#292524;margin-bottom:.75rem;border-bottom:1px solid #e7e5e4;padding-bottom:.5rem}}
  table{{width:100%;border-collapse:collapse}}
  th,td{{text-align:left;padding:.5rem .75rem;border-bottom:1px solid #f5f5f4}}
  th{{background:#f5f5f4;font-weight:600;font-size:.85rem;color:#57534e}}
  td.label{{font-weight:600;width:140px;color:#57534e}}
  .msg{{padding:.5rem 0;border-bottom:1px solid #f5f5f4}}
  .msg:last-child{{border-bottom:none}}
  .sender{{font-weight:600;color:#292524;text-transform:capitalize}}
  .ts{{font-size:.8rem;color:#a8a29e}}
  .msg p{{margin-top:.25rem}}
  .footer{{text-align:center;margin-top:2rem;font-size:.8rem;color:#a8a29e;border-top:1px solid #e7e5e4;padding-top:1rem}}
  @media print{{
    body{{padding:0;background:#fff}}
    .section{{border:1px solid #ccc;break-inside:avoid}}
    .header{{border-bottom:1px solid #ccc}}
  }}
</style>
</head>
<body>
  <div class="header">
    <h1>AI Hotel Suite</h1>
    <div class="meta">
      <strong>{hotel_name}</strong><br>
      Guest ID: {guest_id}<br>
      Exported: {export_date}
    </div>
  </div>

  {pii_html}
  {stays_html}
  {convos_html}

  <div class="footer">GDPR Art.&nbsp;15 — Data Export</div>
</body>
</html>"""

    return HTMLResponse(
        content=html_content,
        headers={"Content-Disposition": f"attachment; filename=guest_{guest_id}_export.html"},
    )


@router.delete("/guests/{guest_id}")
def gdpr_delete_guest(
    guest_id: int,
    db: Session = Depends(get_db),
    _user=Depends(require_staff),
):
    """
    GDPR Erasure — anonymize guest data (soft-delete for referential integrity).
    Deletes GuestPII, clears identifiers, redacts message text.
    """
    if not _user:
        raise HTTPException(status_code=401, detail="Unauthorized")

    guest = (
        db.query(Guest)
        .filter(Guest.id == guest_id, Guest.hotel_id == _user.hotel_id)
        .options(joinedload(Guest.pii))
        .first()
    )
    if not guest:
        raise HTTPException(status_code=404, detail="Guest not found")

    anonymized_count = 0

    # 1. Delete GuestPII record (cascade configured on relationship)
    if guest.pii:
        db.delete(guest.pii)
        anonymized_count += 1

    # 2. Anonymize Guest identifiers
    guest.phone_hash = f"GDPR_DELETED_{guest_id}"
    guest.line_user_id = None
    anonymized_count += 1

    # 3. Redact all messages for this guest's conversations
    conversations = (
        db.query(Conversation)
        .filter(Conversation.guest_id == guest_id, Conversation.hotel_id == _user.hotel_id)
        .all()
    )
    conv_ids = [c.id for c in conversations]
    if conv_ids:
        msg_count = (
            db.query(Message)
            .filter(Message.conversation_id.in_(conv_ids))
            .update(
                {Message.text: "[deleted]", Message.raw_payload_json: None},
                synchronize_session="fetch",
            )
        )
        anonymized_count += msg_count

    db.commit()

    logger.info(
        "GDPR deletion completed for guest %s (hotel %s) by user %s — %d records anonymized",
        guest_id,
        _user.hotel_id,
        _user.email,
        anonymized_count,
    )

    return {"success": True, "anonymized_records": anonymized_count}
