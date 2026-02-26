"""Background job for GDPR data retention (90-day cleanup)."""

import logging
from datetime import datetime, timedelta, timezone

from sqlalchemy.orm import Session

from app.core.db import SessionLocal
from app.models import Conversation, Message, Stay
from app.models.models import GuestPII, StayStatus

logger = logging.getLogger("hotelbot.gdpr_cleanup")

RETENTION_DAYS = 90


def run_gdpr_cleanup() -> dict:
    """
    Delete messages and anonymize guest PII for stays checked out > 90 days ago.

    This implements the data retention policy promised in privacy.html:
    "Conversation History: 90 days by default"

    Returns:
        dict with stats: messages_deleted, guests_anonymized, errors
    """
    db: Session = SessionLocal()
    stats = {"messages_deleted": 0, "guests_anonymized": 0, "conversations_cleaned": 0, "errors": 0}

    try:
        cutoff = datetime.now(timezone.utc) - timedelta(days=RETENTION_DAYS)

        # Find stays that checked out more than 90 days ago
        expired_stays = (
            db.query(Stay)
            .filter(
                Stay.status == StayStatus.POST_STAY,
                Stay.checkout_date < cutoff,
            )
            .all()
        )

        stay_ids = [s.id for s in expired_stays]
        guest_ids = list({s.guest_id for s in expired_stays})

        # 1. Delete messages from conversations linked to expired stays
        if stay_ids:
            expired_conversations = (
                db.query(Conversation).filter(Conversation.stay_id.in_(stay_ids)).all()
            )

            conv_ids = [c.id for c in expired_conversations]
            if conv_ids:
                deleted_count = (
                    db.query(Message)
                    .filter(Message.conversation_id.in_(conv_ids))
                    .delete(synchronize_session="fetch")
                )
                stats["messages_deleted"] = deleted_count
                stats["conversations_cleaned"] = len(conv_ids)

        # 1b. Clean up orphan conversations (BASIC tier, no stay linked) older than 90 days
        orphan_conversations = (
            db.query(Conversation)
            .filter(
                Conversation.stay_id.is_(None),
                Conversation.created_at < cutoff,
            )
            .all()
        )
        orphan_conv_ids = [c.id for c in orphan_conversations]
        if orphan_conv_ids:
            orphan_deleted = (
                db.query(Message)
                .filter(Message.conversation_id.in_(orphan_conv_ids))
                .delete(synchronize_session="fetch")
            )
            stats["messages_deleted"] += orphan_deleted
            stats["conversations_cleaned"] += len(orphan_conv_ids)

        # 2. Anonymize GuestPII for these guests
        # Only anonymize if guest has NO active stays (still checked in elsewhere)
        for guest_id in guest_ids:
            active_stays = (
                db.query(Stay)
                .filter(
                    Stay.guest_id == guest_id,
                    Stay.status.in_([StayStatus.PRE_STAY, StayStatus.IN_HOUSE]),
                )
                .count()
            )
            if active_stays > 0:
                continue  # Guest still active, skip

            pii = db.query(GuestPII).filter(GuestPII.guest_id == guest_id).first()
            if pii and (pii.full_name or pii.phone_plain or pii.email_plain):
                pii.full_name = None
                pii.phone_plain = None
                pii.email_plain = None
                pii.other_pii_json = None
                db.add(pii)
                stats["guests_anonymized"] += 1

        if stats["messages_deleted"] > 0 or stats["guests_anonymized"] > 0:
            db.commit()
            logger.info(
                "[GDPR] Cleanup completed: %d messages deleted, %d guests anonymized, %d conversations cleaned",
                stats["messages_deleted"],
                stats["guests_anonymized"],
                stats["conversations_cleaned"],
            )
        else:
            logger.debug("[GDPR] No data to clean up")

    except Exception as e:
        db.rollback()
        logger.error("[GDPR] Cleanup failed: %s", e, exc_info=True)
        stats["errors"] += 1
    finally:
        db.close()

    return stats
