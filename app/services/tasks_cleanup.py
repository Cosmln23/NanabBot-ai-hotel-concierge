import logging
from datetime import datetime, timedelta, timezone
from typing import Optional

from sqlalchemy.orm import Session
from sqlalchemy.orm.attributes import flag_modified

from app.models import Stay, StayStatus, Task, TaskStatus, TaskType

logger = logging.getLogger("hotelbot.tasks_cleanup")


def _append_note(payload: dict, note: str) -> dict:
    notes = (payload or {}).get("notes", "")
    merged = f"{notes}\n{note}".strip() if notes else note
    payload = payload or {}
    payload["notes"] = merged
    return payload


def run_auto_cleanup(db: Session, now: Optional[datetime] = None) -> dict:
    now = now or datetime.now(timezone.utc)
    closed_checkout = 0
    closed_expired = 0

    # Rule 1: Close open tasks for POST_STAY (except Lost & Found).
    checkout_tasks = (
        db.query(Task)
        .join(Stay, Task.stay_id == Stay.id)
        .filter(
            Task.status.in_([TaskStatus.OPEN, TaskStatus.IN_PROGRESS]),
            Stay.status == StayStatus.POST_STAY,
            Task.type != TaskType.LOST_AND_FOUND,
        )
        .all()
    )
    for task in checkout_tasks:
        task.status = TaskStatus.CANCELLED
        payload = task.payload_json or {}
        task.payload_json = _append_note(payload, "[Auto-closed: Guest checked out]")
        flag_modified(task, "payload_json")
        closed_checkout += 1

    # Rule 2: Expire old FOOD_BEVERAGE / HOUSEKEEPING requests (>24h).
    cutoff = now - timedelta(hours=24)
    expired_tasks = (
        db.query(Task)
        .filter(
            Task.status == TaskStatus.OPEN,
            Task.type.in_([TaskType.FOOD_BEVERAGE, TaskType.HOUSEKEEPING]),
            Task.created_at < cutoff,
        )
        .all()
    )
    for task in expired_tasks:
        task.status = TaskStatus.CANCELLED
        payload = task.payload_json or {}
        task.payload_json = _append_note(payload, "[Auto-closed: Expired > 24h]")
        flag_modified(task, "payload_json")
        closed_expired += 1

    if closed_checkout or closed_expired:
        db.commit()

    summary = {
        "closed_checkout": closed_checkout,
        "closed_expired": closed_expired,
    }
    logger.info("Auto-cleanup completed: %s", summary)
    return summary
