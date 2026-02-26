from datetime import date, datetime, timedelta, timezone
from typing import Any, Dict, Optional

from sqlalchemy import and_
from sqlalchemy.orm import Session

from app.core.logging import logger
from app.models import Hotel, UsageDaily, UsageEvent

MESSAGE_IN = "MESSAGE_IN"
MESSAGE_OUT_BOT = "MESSAGE_OUT_BOT"
MESSAGE_OUT_STAFF = "MESSAGE_OUT_STAFF"
TASK_CREATED = "TASK_CREATED"
TASK_DONE = "TASK_DONE"
LLM_CALL = "LLM_CALL"


def log_event(
    db: Session,
    *,
    hotel_id: int,
    event_type: str,
    value_int: int = 1,
    metadata: Optional[Dict[str, Any]] = None,
) -> None:
    try:
        evt = UsageEvent(
            hotel_id=hotel_id,
            event_type=event_type,
            value_int=value_int,
            metadata_json=metadata or {},
        )
        db.add(evt)
        db.commit()
    except Exception as exc:
        logger.warning("Failed to log usage event %s: %s", event_type, exc)
        db.rollback()


def log_message_in(db: Session, hotel_id: int, metadata: Optional[Dict[str, Any]] = None) -> None:
    log_event(db, hotel_id=hotel_id, event_type=MESSAGE_IN, metadata=metadata)


def log_message_out_bot(
    db: Session, hotel_id: int, metadata: Optional[Dict[str, Any]] = None
) -> None:
    log_event(db, hotel_id=hotel_id, event_type=MESSAGE_OUT_BOT, metadata=metadata)


def log_task_created(db: Session, hotel_id: int, metadata: Optional[Dict[str, Any]] = None) -> None:
    log_event(db, hotel_id=hotel_id, event_type=TASK_CREATED, metadata=metadata)


def log_task_done(db: Session, hotel_id: int, metadata: Optional[Dict[str, Any]] = None) -> None:
    log_event(db, hotel_id=hotel_id, event_type=TASK_DONE, metadata=metadata)


def log_llm_call(
    db: Session,
    hotel_id: int,
    tokens: int = 0,
    metadata: Optional[Dict[str, Any]] = None,
) -> None:
    log_event(
        db,
        hotel_id=hotel_id,
        event_type=LLM_CALL,
        value_int=max(tokens, 1),
        metadata=metadata,
    )


def _date_bounds(day: date) -> tuple[datetime, datetime]:
    start = datetime.combine(day, datetime.min.time())
    end = start + timedelta(days=1)
    return start, end


def aggregate_daily(db: Session, *, target_date: date) -> None:
    start, end = _date_bounds(target_date)
    hotels = db.query(Hotel).all()
    for hotel in hotels:
        events = (
            db.query(UsageEvent)
            .filter(
                UsageEvent.hotel_id == hotel.id,
                UsageEvent.created_at >= start,
                UsageEvent.created_at < end,
            )
            .all()
        )
        if not events:
            continue

        sums: Dict[str, int] = {
            MESSAGE_IN: 0,
            MESSAGE_OUT_BOT: 0,
            MESSAGE_OUT_STAFF: 0,
            TASK_CREATED: 0,
            TASK_DONE: 0,
            LLM_CALL: 0,
        }
        llm_tokens = 0
        for evt in events:
            sums[evt.event_type] = sums.get(evt.event_type, 0) + (evt.value_int or 0)
            if evt.event_type == LLM_CALL:
                llm_tokens += evt.value_int or 0

        existing = (
            db.query(UsageDaily)
            .filter(and_(UsageDaily.hotel_id == hotel.id, UsageDaily.date == target_date))
            .first()
        )
        if not existing:
            existing = UsageDaily(hotel_id=hotel.id, date=target_date)

        existing.messages_in = sums.get(MESSAGE_IN, 0)
        existing.messages_out_bot = sums.get(MESSAGE_OUT_BOT, 0)
        existing.messages_out_staff = sums.get(MESSAGE_OUT_STAFF, 0)
        existing.tasks_created = sums.get(TASK_CREATED, 0)
        existing.tasks_done = sums.get(TASK_DONE, 0)
        existing.llm_calls = sums.get(LLM_CALL, 0)
        existing.llm_tokens = llm_tokens

        db.add(existing)
        db.commit()


def get_daily_usage(db: Session, *, hotel_id: int, days: int = 30) -> list[dict]:
    """Aggregate usage per day for the last N days from UsageEvent."""
    end_date = datetime.now(timezone.utc).date()
    start_date = end_date - timedelta(days=days - 1)

    rows = (
        db.query(UsageEvent)
        .filter(
            UsageEvent.hotel_id == hotel_id,
            UsageEvent.created_at >= datetime.combine(start_date, datetime.min.time()),
            UsageEvent.created_at
            < datetime.combine(end_date + timedelta(days=1), datetime.min.time()),
        )
        .all()
    )

    buckets: dict[date, dict[str, int]] = {}
    for evt in rows:
        day = evt.created_at.date()
        if day not in buckets:
            buckets[day] = {
                "date": day,
                "messages_in": 0,
                "messages_out": 0,
                "tasks_created": 0,
                "tasks_done": 0,
                "llm_calls": 0,
            }
        bucket = buckets[day]
        if evt.event_type == MESSAGE_IN:
            bucket["messages_in"] += evt.value_int or 0
        elif evt.event_type in {MESSAGE_OUT_BOT, MESSAGE_OUT_STAFF}:
            bucket["messages_out"] += evt.value_int or 0
        elif evt.event_type == TASK_CREATED:
            bucket["tasks_created"] += evt.value_int or 0
        elif evt.event_type == TASK_DONE:
            bucket["tasks_done"] += evt.value_int or 0
        elif evt.event_type == LLM_CALL:
            bucket["llm_calls"] += evt.value_int or 0

    # Fill missing days with zeros
    result = []
    for i in range(days):
        day = start_date + timedelta(days=i)
        if day in buckets:
            result.append(
                {
                    "date": buckets[day]["date"].isoformat(),
                    "messages_in": buckets[day]["messages_in"],
                    "messages_out": buckets[day]["messages_out"],
                    "tasks_created": buckets[day]["tasks_created"],
                    "tasks_done": buckets[day]["tasks_done"],
                    "llm_calls": buckets[day]["llm_calls"],
                }
            )
        else:
            result.append(
                {
                    "date": day.isoformat(),
                    "messages_in": 0,
                    "messages_out": 0,
                    "tasks_created": 0,
                    "tasks_done": 0,
                    "llm_calls": 0,
                }
            )

    # sort ascending by date
    result.sort(key=lambda r: r["date"])
    return result
