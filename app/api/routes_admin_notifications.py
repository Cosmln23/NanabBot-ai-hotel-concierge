from datetime import datetime, timezone
from typing import Optional

from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session

from app.api.routes_admin import require_staff
from app.core.db import get_db
from app.models import Conversation, Task

router = APIRouter(prefix="/api/admin/notifications", tags=["admin-notifications"])


def _parse_ts(value: Optional[str]) -> Optional[datetime]:
    if not value:
        return None
    try:
        parsed = datetime.fromisoformat(value)
        if parsed.tzinfo is None:
            parsed = parsed.replace(tzinfo=timezone.utc)
        return parsed
    except Exception:
        return None


@router.get("/check")
def check_notifications(
    last_check: Optional[str] = Query(None),
    db: Session = Depends(get_db),
    staff=Depends(require_staff),
):
    now = datetime.now(timezone.utc)
    if not staff:
        return {
            "has_new": False,
            "new_tasks_count": 0,
            "new_handoff_count": 0,
            "server_time": now.isoformat(),
        }

    since = _parse_ts(last_check)
    if not since:
        return {
            "has_new": False,
            "new_tasks_count": 0,
            "new_handoff_count": 0,
            "server_time": now.isoformat(),
        }

    new_tasks_count = (
        db.query(Task).filter(Task.hotel_id == staff.hotel_id, Task.created_at > since).count()
    )
    priority_rows = (
        db.query(Task.priority)
        .filter(Task.hotel_id == staff.hotel_id, Task.created_at > since)
        .all()
    )
    priority_counts = {"CRITICAL": 0, "URGENT": 0, "NORMAL": 0}
    for (priority,) in priority_rows:
        key = (priority or "NORMAL").upper()
        if key not in priority_counts:
            key = "NORMAL"
        priority_counts[key] += 1

    new_handoff_count = (
        db.query(Conversation)
        .filter(
            Conversation.hotel_id == staff.hotel_id,
            Conversation.updated_at > since,
            Conversation.current_handler == "STAFF",
        )
        .count()
    )

    return {
        "has_new": (new_tasks_count + new_handoff_count) > 0,
        "new_tasks_count": new_tasks_count,
        "new_critical_count": priority_counts["CRITICAL"],
        "new_urgent_count": priority_counts["URGENT"],
        "new_normal_count": priority_counts["NORMAL"],
        "new_handoff_count": new_handoff_count,
        "server_time": now.isoformat(),
    }
